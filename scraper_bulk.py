import asyncio
import time
import scraper
import pandas as pd

logboek_df = pd.read_csv('logboek.csv', sep=';')
urls_not_found = []
others_errors = []

for index, row in logboek_df.iterrows():
    if int(row["scraped"]) == 1:
        continue

    country = row["land"]
    season = row["jaar"]
    league = row["competitienaam"]

    # don't want to get blocked by the website, so we wait a bit before each request
    time.sleep(2)

    try:
        df = asyncio.run(scraper.run_scraper(country, league, season))
        if len(df) > 0:
            df.to_csv(f"./scraped_data/{country}_{league}_{season}.csv", index=False)
            logboek_df.at[index, "scraped"] = 1
        else:
            print(f"No data scraped for {country}, {league}, {season}.")
            urls_not_found.append(f"https://soccerway.com/{country}/{league}-{season}/results/")
    except Exception as e:
        print(f"Error occurred while scraping for {country}, {league}, {season}:  {e}")
        others_errors.append(f"{country}, {league}, {season}: {e}")
        continue

logboek_df.to_csv('logboek.csv', sep=';', index=False)
print("\nScraping completed!")
print("\nURLs not found:")
for url in urls_not_found:
    print(url)
print("\nOther errors:")
for error in others_errors:
    print(error)

    