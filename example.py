from __future__ import print_function, division

import time
import sys
import random
from pprint import pprint
from tournament import Participant, SwissTournament, SingleEliminationTournament


def on_start(tournament):
    print("Starting up an {} player tournament".format(tournament.num_players))


def on_round_complete(tournament):
    print("\n===================")
    print("Round {} Standings".format(tournament.current_round))
    print("===================")
    pprint(list(enumerate(tournament.get_players_by_rank())))


def on_match_ready(tournament, match):
    print("Starting match {} vs. {}".format(match.home, match.away))


def on_match_complete(tournament, match):
    print("Finishing match {} vs {}. Winner: {}".format(match.home, match.away, match.winner))


def on_complete(tournament):
    print("\n===================")
    print("Final Standings")
    print("===================")
    pprint(list(enumerate(tournament.get_players_by_rank())))
    sys.exit()


if __name__ == '__main__':
    participants = [Participant(i) for i in range(1, int(sys.argv[2]) + 1)]
    random.shuffle(participants)

    TOURNAMENTS = dict(
        single=SingleEliminationTournament(participants=participants),
        swiss=SwissTournament(len(participants) // 2, participants=participants),
    )

    example = TOURNAMENTS[sys.argv[1]]
    example.add_callback('on_start', on_start)
    example.add_callback('on_complete', on_complete)
    example.add_callback('on_match_ready', on_match_ready)
    example.add_callback('on_match_complete', on_match_complete)
    example.add_callback('on_round_complete', on_round_complete)
    example.start()

    while True:
        time.sleep(random.random() * 2)
        match = random.choice(example.active_matches)
        match.report_result(random.choice([match.home, match.away]))
