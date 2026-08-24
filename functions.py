### imports
import pandas as pd
import numpy as np
import gurobipy as gp
from gurobipy import GRB

#######################################################
##### create hapset and opponent schedule from df #####
#######################################################

def create_hapset(df):
    """
        Create a hapset from the cleaned df.
        Returns hapset: nxr np.array, 1 means homegame, 0 away
        also returns team_to_index, so we can link the haps to the teams        
    """
    
    teams = list(set(df["team_home"]) | set(df["team_away"]))
    n = len(teams)
    team_to_index = {team: i for i, team in enumerate(teams)}
    r = df["round"].max()
    hapset = np.full((n, r), 2, dtype=int)

    for _, row in df.iterrows():
        home_team = row["team_home"]
        away_team = row["team_away"]
        round_num = row["round"] - 1
        hapset[team_to_index[home_team], round_num] = 1
        hapset[team_to_index[away_team], round_num] = 0
    
    if np.any(hapset == 2):
        print("Warning: Some matches are missing in the dataset.")
    
    return hapset, team_to_index

def get_opponent_schedule(df):
    """
        Constructs the opponent schedule as a 2D array nx(1+r),
        the first column is the team itself and then the next columns 
        are the opponents in each round.
    """
    teams = list(set(df["team_home"]) | set(df["team_away"]))
    n = len(teams)
    r = df["round"].max()
    team_to_index = {team: i for i, team in enumerate(teams)}

    opp_sched = np.zeros((n, r + 1), dtype=object)

    # Fill the first column with team names
    for team, index in team_to_index.items():
        opp_sched[index, 0] = team
    
    # Fill the opponent schedule based on the matches in the DataFrame
    for _, row in df.iterrows():
        home_team = row["team_home"]
        away_team = row["team_away"]
        round_num = row["round"]
        opp_sched[team_to_index[home_team], round_num] = away_team
        opp_sched[team_to_index[away_team], round_num] = home_team

    # Check if any team has an empty opponent slot (indicating missing data)
    if np.any(opp_sched == 0):
        print("Warning: Some matches are missing in the dataset.")

    return opp_sched

####################################################################
############################# Breaks ###############################
####################################################################

def count_breaks(hap):
    count = 0
    for i in range(1, len(hap)):
        if hap[i] == hap[i-1]:
            count += 1
    return count

def count_breaks_hapset(hapset):
    breaks_per_team = []
    for hap in hapset:
        breaks = count_breaks(hap)
        breaks_per_team.append(breaks)
    return breaks_per_team

def count_double_breaks(hap):
    count = 0
    for i in range(2, len(hap)):
        if hap[i] == hap[i-1] == hap[i-2]:
            count += 1
    return count

def calc_min_max_breaks_per_team(hapset):
    breaks_per_team = count_breaks_hapset(hapset)
    min_breaks = min(breaks_per_team)
    max_breaks = max(breaks_per_team)
    team_min = []
    team_max = []
    for ind, el in enumerate(breaks_per_team):
        if el == min_breaks:
            team_min.append(ind)
        if el == max_breaks:
            team_max.append(ind)
    return (team_min, min_breaks), (team_max, max_breaks)

def is_equitable_hapset(hapset):
    breaks_per_team = count_breaks_hapset(hapset)
    return len(set(breaks_per_team)) == 1

def has_no_start_end_breaks(hapset):
    for hap in hapset:
        if hap[0] == hap[1] or hap[-1] == hap[-2]:
            return False
    print("Schedule has no start/end breaks.")
    return True

def has_no_double_breaks(hapset):
    for hap in hapset:
        if count_double_breaks(hap) > 0:
            return False
    print("Schedule has no consecutive breaks.")
    return True

def calc_max_consec_H_or_A(hapset):
    max_consec_breaks = 0
    for hap in hapset:
        consec_breaks = 0
        for i in range(1, len(hap)):
            if hap[i] == hap[i-1]:
                consec_breaks += 1
                max_consec_breaks = max(max_consec_breaks, consec_breaks)
            else:
                consec_breaks = 0
    return max_consec_breaks

def check_AAHAA_occurence(hapset):
    r = hapset.shape[1]
    AAHAA = np.array([0,0,1,0,0])

    for hap in hapset:
        for i in range(r - 4):
            if np.array_equal(hap[i: i + 5], AAHAA):
                return True

    return False

########################################################################
############################# Symmetry #################################
########################################################################

def is_kRR(n, r):
    return r == 2*(n-1) or r == 3*(n-1) or r == 4*(n-1)

def calc_seperation(df):
    teams = list(set(df["team_home"]) | set(df["team_away"]))
    n = len(teams)
    r = df["round"].max()

    if not is_kRR(n, r):
        print("Not a k-RR schedule, separation is not defined.")
        return None
    
    df = df.sort_values(by="round")
    min_dif = 1000

    for _, row in df.iterrows():
        h_team = row["team_home"]
        a_team = row["team_away"]
        curr_round = row["round"]

        # find the next match of the same teams
        next_match = df[((df["team_home"] == a_team) & (df["team_away"] == h_team)) & (df["round"] > curr_round)]

        if not next_match.empty:
            next_round = next_match["round"].values[0]
            dif = next_round - curr_round
            if dif < min_dif:
                min_dif = dif
    return min_dif

def is_phased(df):
    teams = list(set(df["team_home"].unique()) | set(df["team_away"].unique()))
    n = len(teams)
    r = df["round"].max()
    if not is_kRR(n, r):
        print("Not a k-RR schedule, separation is not defined.")
        return None
    
    separation = calc_seperation(df)
    return separation >= n-1

def is_mirrored(df):
    if not is_phased(df):
        print("Not a phased schedule, cannot be mirrored.")
        return False
    
    matchups = np.sort(df[['team_home', 'team_away']].values, axis=1)
    df_copy = df.copy()
    df_copy["matchup"] = matchups[:, 0] + "_" + matchups[:, 1]

    gaps = df_copy.groupby("matchup")["round"].max() - df_copy.groupby("matchup")["round"].min()

    if any(gaps != (df["round"].max() - df["round"].min()) // 2):
        return False
    print("Schedule is mirrored.")
    return True

def is_english(df):
    if not is_phased(df):
        print("Not a phased schedule, cannot be English.")
        return False
    n = len(set(df["team_home"].unique()) | set(df["team_away"].unique()))

    for _, row in df.iterrows():
        h_team = row["team_home"]
        a_team = row["team_away"]
        curr_round = row["round"]

        if curr_round == n:
            break

        # find the next match of the same teams
        if curr_round == n - 1:
            next_match = df[((df["team_home"] == a_team) & (df["team_away"] == h_team)) & (df["round"] == curr_round + 1)]
        else:
            next_match = df[((df["team_home"] == a_team) & (df["team_away"] == h_team)) & (df["round"] == curr_round + n)]

        if next_match.empty:
            return False

    print("Schedule is English.")
    return True

def check_specific_match(df, team1, team2):
    return df[((df["team_home"] == team1) & (df["team_away"] == team2)) | ((df["team_home"] == team2) & (df["team_away"] == team1))]

def is_french(df):
    if not is_phased(df):
        print("Not a phased schedule, cannot be French.")
        return False
    n = len(set(df["team_home"].unique()) | set(df["team_away"].unique()))

    for _, row in df.iterrows():
        h_team = row["team_home"]
        a_team = row["team_away"]
        curr_round = row["round"]
        
        if curr_round == n:
            break

        # find the next match of the same teams
        if curr_round == 1:
            next_match = df[((df["team_home"] == a_team) & (df["team_away"] == h_team)) & (df["round"] == 2*n - 2)]
        else:
            next_match = df[((df["team_home"] == a_team) & (df["team_away"] == h_team)) & (df["round"] == curr_round + n - 2)]

        if next_match.empty:
            return False

    print("Schedule is French.")
    return True

###########################################################################
############################### Canonical #################################
###########################################################################

def get_one_factors_from_opp_sched(opp_sched):
    """
        Creates the one-factor of every round from the opponent schedule.
        Returns this as a list (duplicate one factors possible)
    """
    n = opp_sched.shape[0]
    rounds = opp_sched.shape[1] - 1 # first col is team names
    one_factors = []
    

    for r in range(1, rounds + 1):
        round_set = set()
        for i in range(n):
            team = opp_sched[i, 0] # team name
            opp = opp_sched[i, r] # opponent of i in round r
            game = frozenset([team, opp])
            # if the game was already in the set it will not be added
            round_set.add(game) 
        one_factors.append(frozenset(round_set))

    return one_factors

def get_canonical_indexes(n, i):
    """
        Creates the canonical one factor based on the teams size and i
        returns a dictionary with for every index which index 
        it would face in the canonical round i, index starts at 1
    """
    lookup = {}
    lookup[i] = n
    lookup[n] = i

    for k in range(1, n//2):
        team1 = (i + k) % (n-1)
        team2 = (i - k) % (n-1)

        team1 = n-1 if team1 == 0 else team1
        team2 = n-1 if team2 == 0 else team2

        lookup[team1] = team2
        lookup[team2] = team1

    return lookup

def convert_teamlist_to_onefactors(team_order):
    """
        Create the canonical schedule given a team order. last team is the fixed team
    """
    n = len(team_order)
    team_list = [0] + team_order
    one_factors = []

    for i in range(1, n):
        lookup = get_canonical_indexes(n, i)
        round_set = set()
        for key, value in lookup.items():
            round_set.add(frozenset([team_list[key], team_list[value]]))
        one_factors.append(frozenset(round_set))
    
    return one_factors

def build_canonical_one_factors(round1, round2, fixed_team, team_list):
    """
        Given two rounds and a fixed team, 
        Create the team_order on which a canonical schedule could be made
    """
    n = len(team_list)
    last_pos = n - 1
    team_order = [None] * n
    team_order[last_pos] = fixed_team
    opposites_r1 = {}
    opposites_r2 = {}
    F1 = get_canonical_indexes(n, 1)
    F2 = get_canonical_indexes(n, 2)

    # get team1 as opp of fixedteam in round 1
    for pair in round1:
        pair = list(pair)
        if fixed_team in pair:
            team_order[0] = pair[0] if pair[1] == fixed_team else pair[1]
        else: 
            # get opposites from round 1
            opposites_r1[pair[0]] = pair[1]
            opposites_r1[pair[1]] = pair[0]
    
    # get team2 from round 2
    for pair in round2:
        pair = list(pair)
        if fixed_team in pair:
            team_order[1] = pair[0] if pair[1] == fixed_team else pair[1]
        else: 
            # get opposites from round 2
            opposites_r2[pair[0]] = pair[1]
            opposites_r2[pair[1]] = pair[0]

    idx = 2
    while None in team_order:
        print(f"Current known order: {team_order}")
        # first fill in from round 1 by getting opposite of team2
        opp_idx = F1[idx]
        current_team = team_order[idx - 1]
        print(f"current_team: {current_team}")
        opp_team = opposites_r1[current_team]
        print(f"opp_team: {opp_team}")
        team_order[opp_idx - 1] = opp_team

        # then fill in from F
        idx = F2[opp_idx]
        print(f"new index = {idx}")
        new_team =  opposites_r2[opp_team]
        team_order[idx - 1] = new_team

    return convert_teamlist_to_onefactors(team_order)

def is_canonical_schedule(opp_sched):
    n = opp_sched.shape[0]
    r = opp_sched.shape[1] - 1
    list_of_teams = list(opp_sched[:, 0])

    one_factors_to_check = get_one_factors_from_opp_sched(opp_sched)

    if len(set(one_factors_to_check)) != n - 1:
        print("Too many different one factors in schedule")
        return False
    
    for r_ind1 in range(r):
        round1 = one_factors_to_check[r_ind1]
        for r_ind2 in range(r_ind1 + 1, r):
            round2 = one_factors_to_check[r_ind2]
            for fixed_team in list_of_teams:
                can_one_factors = build_canonical_one_factors(round1, round2, fixed_team, list_of_teams)
                if set(can_one_factors) == set(one_factors_to_check):
                    print("Schedule is canonical")
                    return True
    
    print("No matching one factors found!")
    return False
    
#########################################################################
############################# Balancedness ##############################
#########################################################################

def is_balanced(hapset):
    r = hapset.shape[1]
    odd = r % 2 == 1
    for hap in hapset:
        if odd:
            if np.sum(hap) not in [r//2, r//2 + 1]:
                return False
        else:
            if np.sum(hap) != r//2:
                return False
    return True

def calc_k_balanced(hapset):
    """
     calculates the k.
     Which is the max difference between home games and away games
     after every round for every team
    """
    k = 0
    r = hapset.shape[1]

    for i in range(2, r + 1):
        hapset_k = hapset[:, :i]
        homes = np.sum(hapset_k, axis=1)
        aways = i - homes
        balance_r = np.abs(homes - aways)
        k = max(k, np.max(balance_r))
    return k


def calc_g_balanced(hapset):
    """
        g is the maximal difference between the number of homegames played 
        between all teams after every round 
    """
    g = 0
    r = hapset.shape[1]

    for i in range(2, r+1):
        hapset_k = hapset[:, :i]
        homes = np.sum(hapset_k, axis=1)
        g = max(g, np.max(homes) - np.min(homes))
    return g

#####################################################################
########################### Carry-over ##############################
#####################################################################

def calc_carry_over_effect(opp_sched, wrap_around = True, normalized = True):
    n = opp_sched.shape[0]
    # only keep n-1 first rounds
    opp_sched = opp_sched[:,:n]
    r = opp_sched.shape[1] - 1

    carry_over_matrix = np.zeros((n, n), dtype=int)

    for i in range(n):
        for j in range(n):
            if i == j:
                continue

            carry_count = 0
            
            # count carry-over
            if wrap_around: max_range = r+1 
            else: max_range = r
            for rnd in range(1, max_range):
                if rnd == r: # WRAP AROUND
                    opponent_i = opp_sched[i, rnd]
                    opponent_j = opp_sched[j, 1]
                else:
                    opponent_i = opp_sched[i, rnd]
                    opponent_j = opp_sched[j, rnd + 1]

                if opponent_i == opponent_j:
                    carry_count += 1

            carry_over_matrix[i,j] = carry_count

    print(carry_over_matrix)
    tot_carry_over = np.sum(np.square(carry_over_matrix))
    # n^3 − 7n2 + 18n − 12
    max_carry_possible = n ** 3 - 7 * n ** 2 + 18 * n - 12
    if normalized:
        return tot_carry_over/max_carry_possible, carry_over_matrix
    return tot_carry_over, carry_over_matrix

################################################################################
############################### Flexibility ####################################
################################################################################

# flexibility
def lambers_IP_checker_SRR(hapset: np.ndarray, team1: int, team2: int, l: int):
    """
        Checks wether given a hapset and a fixed game (team1 vs team2 at round l)
        it is possible to create a valid schedule
    """
    n_teams = hapset.shape[0]
    model = gp.Model("briskorn_condition")
    model.Params.OutputFlag = 0
    
    x = {}
    for i in range(n_teams):
        for j in range(i+1, n_teams):
            for r in range(n_teams - 1):
                x[i,j,r] = model.addVar(vtype=GRB.BINARY, name=f"x_{i}_{j}_{r}")

    for i in range(n_teams):
        for p in range(n_teams - 1):
            sum_last = gp.quicksum(x[j, i, p] for j in range(n_teams) if j < i)
            sum_first = gp.quicksum(x[i, j, p] for j in range(n_teams) if j > i)
            model.addConstr(sum_first + sum_last == 1, name=f"Constr_One_Game_{i}_{p}")

    for i in range(n_teams):
        for j in range(i+1, n_teams):
            model.addConstr(
                gp.quicksum(x[i, j, p] for p in range(n_teams - 1)) == 1, 
                name=f"Constr_Pair_{i}_{j}"
            )
    
    for i in range(n_teams):
        for j in range(i+1, n_teams):
            for r in range(n_teams - 1):
                if hapset[i, r] == hapset[j, r]:
                    model.addConstr(x[i,j,r] == 0, name=f"Constr_HAP_{i}_{j}_{r}")

    if team1 > team2:
        team1, team2 = team2, team1
    model.addConstr(x[team1, team2, l] == 1, name=f"Constr_Force_{team1}_{team2}_{l}")
    
    model.optimize()

    is_feasible = model.status == GRB.OPTIMAL
    schedule = []
    if is_feasible:
        schedule = [(i, j, r) for (i, j, r), var in x.items() if var.X > 0.5]
        
    model.dispose()
    return int(is_feasible), schedule

def lambers_IP_checker_DRR(hapset: np.ndarray, home_team: int, away_team: int, l: int):
    """
        Checks wether given a hapset and a fixed game (team1 vs team2 at round l)
        it is possible to create a valid schedule
    """
    n_teams = hapset.shape[0]
    n_rounds = hapset.shape[1]  # should be 4*(n_teams//2) - 2

    model = gp.Model("drr_spread")
    model.Params.OutputFlag = 0

    # x[i,j,r] = 1 means team i hosts team j in round r (ordered)
    x = {}
    for i in range(n_teams):
        for j in range(n_teams):
            if i == j:
                continue
            for r in range(n_rounds):
                x[i, j, r] = model.addVar(vtype=GRB.BINARY, name=f"x_{i}_{j}_{r}")

    # Each ordered match (i,j) is played exactly once
    for i in range(n_teams):
        for j in range(n_teams):
            if i == j:
                continue
            model.addConstr(
                gp.quicksum(x[i, j, r] for r in range(n_rounds)) == 1,
                name=f"match_{i}_{j}"
            )

    # Each team plays exactly one match per round
    for i in range(n_teams):
        for r in range(n_rounds):
            model.addConstr(
                gp.quicksum(x[i, j, r] for j in range(n_teams) if j != i)   # i at home
                + gp.quicksum(x[j, i, r] for j in range(n_teams) if j != i) # i away
                == 1,
                name=f"one_game_{i}_{r}"
            )

    # HAP compatibility:
    # x[i,j,r]=1 requires hapset[i,r]=1 (i is home) and hapset[j,r]=0 (j is away)
    for i in range(n_teams):
        for j in range(n_teams):
            if i == j:
                continue
            for r in range(n_rounds):
                if hapset[i, r] != 1 or hapset[j, r] != 0:
                    model.addConstr(x[i, j, r] == 0)

    # Force the specific match into round l
    model.addConstr(x[home_team, away_team, l] == 1,
                    name=f"force_{home_team}_{away_team}_{l}")

    model.optimize()

    is_feasible = model.status == GRB.OPTIMAL
    schedule = []
    if is_feasible:
        schedule = [(i, j, r) for (i, j, r), var in x.items() if var.X > 0.5]

    model.dispose()
    return int(is_feasible), schedule


def spread_calculator(hapset: np.ndarray, is_drr: bool) -> int:
    n_teams = hapset.shape[0]
    r_rounds = hapset.shape[1]
    matches_seen = set()
    total_spread = 0

    pairs = (
        [(i, j) for i in range(n_teams) for j in range(n_teams) if i != j]
        if is_drr else
        [(i, j) for i in range(n_teams) for j in range(i+1, n_teams)]
    )

    for i, j in pairs:
        for r in range(r_rounds):
            if is_drr:
                skip_condition = hapset[i, r] == 0 or hapset[j, r] == 1 or (i, j, r) in matches_seen
            else:
                skip_condition = hapset[i, r] == hapset[j, r] or (i, j, r) in matches_seen
            if skip_condition:
                continue
            if is_drr:
                feas, sched = lambers_IP_checker_DRR(hapset, i, j, r)
            else:
                feas, sched = lambers_IP_checker_SRR(hapset, i, j, r)
            if feas:
                for match in sched:
                    if match not in matches_seen:
                        total_spread += 1
                        matches_seen.add(match)
    
    ub_spread = n_teams * (n_teams - 1)/4
    print(f"Total spread: {total_spread}/{ub_spread}")
    return total_spread/ub_spread

def lambers_IP_FP_SRR(hapset: np.ndarray, team1: int, team2: int):
    """
        Given a hapset and two teams it checks wether there can be two 
        schedules generated where team1 vs team2 is in different rounds.
        If this is the case the game is not fixed.
    """
    n_teams = hapset.shape[0]
    n_rounds = n_teams - 1
    W = 2

    if team1 > team2:
        team1, team2 = team2, team1

    model = gp.Model("FP_SRR")
    model.Params.OutputFlag = 0

    x = {}
    for w in range(W):
        for i in range(n_teams):
            for j in range(i + 1, n_teams):
                for r in range(n_rounds):
                    x[w, i, j, r] = model.addVar(vtype=GRB.BINARY, name=f"x_{w}_{i}_{j}_{r}")

    # Each match played exactly once per schedule
    for w in range(W):
        for i in range(n_teams):
            for j in range(i + 1, n_teams):
                model.addConstr(
                    gp.quicksum(x[w, i, j, r] for r in range(n_rounds)) == 1,
                    name=f"match_{w}_{i}_{j}"
                )

    # Each team plays exactly once per round per schedule
    for w in range(W):
        for i in range(n_teams):
            for r in range(n_rounds):
                model.addConstr(
                    gp.quicksum(x[w, i, j, r] for j in range(i + 1, n_teams))
                    + gp.quicksum(x[w, j, i, r] for j in range(i))
                    == 1,
                    name=f"one_game_{w}_{i}_{r}"
                )

    # HAP compatibility
    for w in range(W):
        for i in range(n_teams):
            for j in range(i + 1, n_teams):
                for r in range(n_rounds):
                    if hapset[i, r] == hapset[j, r]:
                        model.addConstr(x[w, i, j, r] == 0)

    # Target match {team1, team2} must be in different rounds across the two schedules
    for r in range(n_rounds):
        model.addConstr(
            gp.quicksum(x[w, team1, team2, r] for w in range(W)) <= 1,
            name=f"diff_round_{r}"
        )

    model.optimize()

    is_fixed = model.status != GRB.OPTIMAL
    model.dispose()
    return int(is_fixed)


def lambers_IP_FP_DRR(hapset: np.ndarray, home_team: int, away_team: int):
    """
        Given a hapset and two teams it checks wether there can be two 
        schedules generated where team1 vs team2 is in different rounds.
        If this is the case the game is not fixed.
    """
    n_teams = hapset.shape[0]
    n_rounds = hapset.shape[1]
    W = 2

    model = gp.Model("FP_DRR")
    model.Params.OutputFlag = 0

    x = {}
    for w in range(W):
        for i in range(n_teams):
            for j in range(n_teams):
                if i == j:
                    continue
                for r in range(n_rounds):
                    x[w, i, j, r] = model.addVar(vtype=GRB.BINARY, name=f"x_{w}_{i}_{j}_{r}")

    # Each ordered match (i,j) played exactly once per schedule
    for w in range(W):
        for i in range(n_teams):
            for j in range(n_teams):
                if i == j:
                    continue
                model.addConstr(
                    gp.quicksum(x[w, i, j, r] for r in range(n_rounds)) == 1,
                    name=f"match_{w}_{i}_{j}"
                )

    # Each team plays exactly once per round per schedule
    for w in range(W):
        for i in range(n_teams):
            for r in range(n_rounds):
                model.addConstr(
                    gp.quicksum(x[w, i, j, r] for j in range(n_teams) if j != i)
                    + gp.quicksum(x[w, j, i, r] for j in range(n_teams) if j != i)
                    == 1,
                    name=f"one_game_{w}_{i}_{r}"
                )

    # HAP compatibility
    for w in range(W):
        for i in range(n_teams):
            for j in range(n_teams):
                if i == j:
                    continue
                for r in range(n_rounds):
                    if hapset[i, r] != 1 or hapset[j, r] != 0:
                        model.addConstr(x[w, i, j, r] == 0)

    # target match (home_team, away_team) must be in different rounds
    for r in range(n_rounds):
        model.addConstr(
            gp.quicksum(x[w, home_team, away_team, r] for w in range(W)) <= 1,
            name=f"diff_round_{r}"
        )

    model.optimize()

    is_fixed = model.status != GRB.OPTIMAL
    model.dispose()
    return int(is_fixed)


def fixed_part_calculator(hapset, is_drr):
    n_teams = hapset.shape[0]
    fp = 0
    for i in range(n_teams):
        for j in range(i + 1, n_teams):
            if is_drr:
                fp += lambers_IP_FP_DRR(hapset, i, j)
            else: 
                fp += lambers_IP_FP_SRR(hapset, i, j)
    print(f"Fixed part: {fp}/{int(n_teams * (n_teams-1)/2)}")
    return fp/(n_teams * (n_teams-1)/2)

