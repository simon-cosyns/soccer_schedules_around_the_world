import xml.etree.ElementTree as ET
import subprocess


class XMLInstanceBuilderRR:
    def __init__(self, instanceName, nRR, league_size, compactness="C", total_slots = None):
        """
        instanceName: str, name of the instance (e.g., "Land_Seizoen")
        nRR: int, number of round robins (e.g., 2 for double round robin)
        league_size: int, number of teams in the league 
        compactness: str, "C" for compact schedule, "R" for time-relaxed schedule
        total_slots: int, total number of slots (only needed for time-relaxed schedules)
        """
        # Root
        self.root = ET.Element("Instance")

        # --- MetaData ---
        metadata = ET.SubElement(self.root, "MetaData")
        self.instanceName = instanceName
        ET.SubElement(metadata, "InstanceName").text = instanceName # Ik stel voor Land_Seizoen
        ET.SubElement(metadata, "DataType").text = "R" # R staat voor echte real-world data, A voor artificieel
        ET.SubElement(metadata, "Contributor").text = "Cosyns, Wessel, Goossens and Spieksma"
        ET.SubElement(metadata, "Date", year="2026")
        ET.SubElement(metadata, "Remarks").text = f"Schedule of {instanceName}"

        # --- Structure ---
        structure = ET.SubElement(self.root, "Structure")
        fmt = ET.SubElement(structure, "Format", leagueIds="0") # verplicht voor RobinX
        ET.SubElement(fmt, "numberRoundRobin").text = str(nRR)
        ET.SubElement(fmt, "compactness").text = compactness # C = compact, R = time-relaxed
        ET.SubElement(fmt, "gameMode").text = "NULL"  # symmetrie in schedule: Null = geen, M = mirrored, P = Phased, F = French, E = English
        # ET.SubElement(structure, "AdditionalGames") # voor non RR torunaments

        # --- ObjectiveFunction ---
        obj = ET.SubElement(self.root, "ObjectiveFunction") # verplicht voor RobinX
        ET.SubElement(obj, "Objective").text = "NONE"

        # --- Data ---
        data = ET.SubElement(self.root, "Data") # verplicht voor RobinX
        self.distances_node = ET.SubElement(data, "Distances")
        ET.SubElement(data, "COEWeights")
        ET.SubElement(data, "Costs")

        # --- Resources ---
        resources = ET.SubElement(self.root, "Resources")

        #team_groups = ET.SubElement(resources, "TeamGroups")  # Voor conferenties zoals in de USA
        #ET.SubElement(team_groups, "teamGroup", id="0", name="All teams")

        ET.SubElement(resources, "LeagueGroups") # verplicht voor RobinX

        self.leagues_node = ET.SubElement(resources, "Leagues")
        ET.SubElement(self.leagues_node, "league", id="0", name="All teams") # verplicht voor RobinX
        self.teams_node = ET.SubElement(resources, "Teams")

        ET.SubElement(resources, "SlotGroups")
        if compactness == "C":
            total_slots = nRR * (league_size - 1) # rondes nodig bij compact schedule

        self.slots_node = ET.SubElement(resources, "Slots")
        for i in range(total_slots):
            ET.SubElement(self.slots_node, "slot", id=str(i), name=f"Slot {i}")

        # --- Constraints ---
        constraints = ET.SubElement(self.root, "Constraints") # verplicht voor RobinX, maar wij hebben geen constraints
        ET.SubElement(constraints, "BasicConstraints")
        ET.SubElement(constraints, "CapacityConstraints")
        ET.SubElement(constraints, "GameConstraints")
        ET.SubElement(constraints, "BreakConstraints")
        ET.SubElement(constraints, "FairnessConstraints")
        ET.SubElement(constraints, "SeparationConstraints")
        
    # --- Add functions ---
    def addTeam(self, teamId, name):
        ET.SubElement(
            self.teams_node,
            "team",
            id=str(teamId),
            league="0", # verplicht voor RobinX, wij hebben maar 1 league
            name=name
        )

    def addTeams(self, teams):
        """
        teams = [(teamId, team_name), ...]
        """
        for teamId, name in teams:
            self.addTeam(teamId, name)

    def addLeague(self, leagueId, name):
        ET.SubElement(
            self.leagues_node,
            "league",
            id=str(leagueId),
            name=name
        )

    def addSlot(self, slotId, name):
        ET.SubElement(
            self.slots_node,
            "slot",
            id=str(slotId),
            name=name
        )

    def save(self):
        self._indent(self.root)
        tree = ET.ElementTree(self.root)
        tree.write(f"./xml_files/{self.instanceName}_instance.xml", encoding="utf-8", xml_declaration=True)

    # Pretty print
    def _indent(self, elem, level=0):
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            for child in elem:
                self._indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i

class XMLSolutionBuilder:
    def __init__(self, instanceName):
        """
        instanceName: Gebruik dezelfde instanceName als in XMLInstanceBuilderRR
        """
        # Root
        self.root = ET.Element("Solution")

        # --- MetaData ---
        metadata = ET.SubElement(self.root, "MetaData")
        self.instanceName = instanceName
        ET.SubElement(metadata, "SolutionName").text = f"{instanceName}_sched"
        ET.SubElement(metadata, "InstanceName").text = instanceName
        ET.SubElement(metadata, "Contributor").text = "Cosyns, Wessel, Goossens and Spieksma"
        ET.SubElement(metadata, "Date",year="2026")
        ET.SubElement(metadata, "ObjectiveValue", infeasibility="0", objective="0")
        ET.SubElement(metadata, "Remarks").text = f"Schedule of {instanceName}"

        # --- Games ---
        self.games_node = ET.SubElement(self.root, "Games")

    # Add a scheduled match
    def addGame(self, home, away, slot):
        ET.SubElement(
            self.games_node,
            "ScheduledMatch",
            home=str(home),
            away=str(away),
            slot=str(slot)
        )

    # Optional: batch add
    def addGames(self, games):
        """
        games = [(home, away, slot), ...]
        """
        for home, away, slot in games:
            self.addGame(home, away, slot)

    def save(self):
        self._indent(self.root)
        tree = ET.ElementTree(self.root)
        tree.write(f"./xml_files/{self.instanceName}_sched.xml", encoding="utf-8", xml_declaration=True)

    # Pretty print
    def _indent(self, elem, level=0):
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            for child in elem:
                self._indent(child, level + 1)
            if not child.tail or not child.tail.strip():
                child.tail = i
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


# Minimal example
def main():
    instance = XMLInstanceBuilderRR("ExampleInstance", nRR=2, league_size=4, compactness="C")

    # Add teams, one by one
    instance.addTeam(0, "ATL")
    instance.addTeam(1, "NYM")
    instance.addTeam(2, "PHI")
    instance.addTeam(3, "MON")

    # Add all teams at once
    # teams = [
    #     (0, "ATL"),
    #     (1, "NYM"),
    #     (2, "PHI"),
    #     (3, "MON")
    # ]
    # instance.addTeams(teams) # teams = [(teamId, team_name), ...]

    instance.save()
    print("Generated instance.xml from scratch!")

    solution = XMLSolutionBuilder("ExampleInstance")

    # Add games one by one
    solution.addGame(1,0,1)
    solution.addGame(0,1,4)
    solution.addGame(2,0,0)
    solution.addGame(0,2,3)
    solution.addGame(3,0,2)
    solution.addGame(0,3,5)
    solution.addGame(2,1,5)
    solution.addGame(1,2,2)
    solution.addGame(3,1,0)
    solution.addGame(1,3,3)
    solution.addGame(3,2,1)
    solution.addGame(2,3,4)

    # Add all games at once
    # game_list = [
    #     (1,0,1), (0,1,4), (2,0,0), (0,2,3), (3,0,2), (0,3,5),
    #     (2,1,5), (1,2,2), (3,1,0), (1,3,3), (3,2,1), (2,3,4)
    # ]
    # solution.addGames([game_list]) # game_list = [(home, away, slot), ...]


    solution.save()
    print(f"Generated solution.xml from scratch!")

    #subprocess.run("../RobinX -i instance.xml -s solution.xml", shell=True)


if __name__ == "__main__":
    main()
