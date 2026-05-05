"""
Scraped data van soccerway.com en geconverteerd naar XML formaat voor gebruik in RobinX.
voor gebruik gewoon de gewenste parameters aanpassen in de main functie en het script runnen.
"""

import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import pandas as pd
from converter import XMLInstanceBuilderRR, XMLSolutionBuilder

async def run_scraper(country, league, season):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        data_list = []

        print(f"Navigating to {league} Results...")
        await page.goto(f"https://soccerway.com/{country}/{league}-{season}/results/", wait_until="domcontentloaded")

        print("Attempting to auto-dismiss cookie banner...")
        try:
            accept_button = page.locator('button[id="onetrust-accept-btn-handler"]')
            await accept_button.wait_for(timeout=5000)
            await accept_button.click()
            print("Cookie banner dismissed.")
        except:
            print("No cookie banner found, continuing...")


        print("Starting to load all matches. This might take a few moments...")
        
        while True:
            # Locate the 'Show more matches' button using the testid you found
            show_more_button = page.locator('button[data-testid="wcl-buttonLink"]')
            
            # Check if it exists and is visible
            if await show_more_button.is_visible():
                print("Clicking 'Show more matches'...")
                await show_more_button.click()
                
                # We must wait for the site to load the new content
                # 2 seconds wait to avoid getting blocked
                await page.wait_for_timeout(2000) 
            else:
                print("All matches loaded! Proceeding to scrape...")
                break

        # Capture the final fully-expanded page
        html = await page.content()
        soup = BeautifulSoup(html, "html.parser")

        # Find all round headers and match rows
        elements = soup.find_all('div', class_=lambda x: x and x.startswith('event__'))

        print(f"Analyzing {len(elements)} elements...\n")

        current_round = "Unknown Round"
        
        for el in elements:
            class_list = el.get('class', [])
            
            # 1. Update the Round Header
            if 'event__round' in class_list:
                current_round = el.get_text(strip=True)
                print(f"\n--- {current_round} ---")
                continue
            
            # 2. Extract Match Row
            if 'event__match' in class_list:
                full_text = el.get_text(" | ", strip=True)
                parts = full_text.split(" | ")
                print(f"Match found: {full_text}")

                # Store match data
                # We assume the format is: Date | Team Home | Team Away | (optional score or status)
                if len(parts) >= 3:
                    if parts[1].isnumeric(): # Handle cases with red cards manually
                        print(f"Warning: Unexpected format for match row (possible red card info): {full_text}")
                        parts.insert(1, input("Enter home team: "))  # Insert a placeholder for team_home
                    if parts[2].isnumeric(): # Handle cases with red cards manually
                        print(f"Warning: Unexpected format for match row (possible red card info): {full_text}")
                        parts.insert(2, input("Enter away team: "))  # Insert a placeholder for team_away
                    data_list.append({
                        "round":     current_round,
                        "date":      parts[0],
                        "team_home": parts[1],
                        "team_away": parts[2],
                        "full_text": full_text
                    })
                else:
                    print(f"Warning: Unexpected format for match row: {full_text}")
                    data_list.append({
                        "round":     current_round,
                        "date":      "NA",
                        "team_home": "NA",
                        "team_away": "NA",
                        "full_text": full_text
                    })


        print("\nScraping finished.")
        await browser.close()
        df = pd.DataFrame(data_list)

        return df
    
def generate_xml(df, instance_name):
    """
    df: DataFrame with columns [round, date, team_home, team_away]
    instance_name: str, name for the XML files (e.g. "country_league_season")
    """

    # --- Build team list ---
    all_teams = pd.concat([df['team_home'], df['team_away']]).unique()
    team_to_id = {team: i for i, team in enumerate(sorted(all_teams))}
    league_size = len(team_to_id)

    # --- Build round list ---
    rounds = df['round'].unique()
    round_to_slot = {round_name: i for i, round_name in enumerate(rounds)}

    # get NRR
    compactness = "C"  # Assuming compactness is always "C" for now
    exact = len(rounds) / (league_size - 1)   # normal division
    nRR = round(exact)
    if abs(exact - nRR) > 0.01:  
        print(f"Warning: rounds ({len(rounds)}) does not match expected nRR ({nRR}) for league size {league_size}.")
        nRR = int(input("Enter nRR manually: "))
        compactness = input("Enter compactness (C or R): ")

    # --- Instance XML ---
    instance = XMLInstanceBuilderRR(instance_name, nRR=nRR, league_size=league_size, compactness=compactness)
    for team, team_id in sorted(team_to_id.items(), key=lambda x: x[1]):
        instance.addTeam(team_id, team)
    instance.save()
    print(f"Instance XML saved: {instance_name}_instance.xml")

    # --- Solution XML ---
    solution = XMLSolutionBuilder(instance_name)
    for _, row in df.iterrows():
        home_id = team_to_id[row['team_home']]
        away_id = team_to_id[row['team_away']]
        slot    = round_to_slot[row['round']]
        solution.addGame(home_id, away_id, slot)
    solution.save()
    print(f"Solution XML saved: {instance_name}_sched.xml")

if __name__ == "__main__":
    # AANPASSEN NAAR WENSEN
    country = "mexico" # naam van het land voor URL kleine letters en engelse naam
    season = "2024-2025" # seizoen in format "YYYY-YYYY" (e.g. "2023-2024")
    league = "liga-mx" # naam van de competitie spatie wordt een streepje (e.g. "liga-mx", "premier-league", "la-liga")
    
    instance_name = f"{country}_{league}_{season}"

    # Scrape the data
    df = asyncio.run(run_scraper(country, league, season))
    df.to_csv(f"./scraped_data/{country}_{league}_{season}.csv", index=False)

    # Generate XML files
    generate_xml(df, instance_name)
