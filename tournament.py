import uuid
import math
from collections import deque


class Participant(object):
    def __init__(self, pid):
        self.id = pid
        self.current_match = None
        self.match_history = list()
        self.tournament_score = 0

    def set_current_match(self, match):
        self.current_match = match
        self.match_history.append(match)

    def __eq__(self, other):
        return isinstance(other, Participant) and self.id == other.id

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "Player {} [{}]".format(self.id, self.tournament_score)


BY = Participant("BY")


class Match(object):
    TIE = 1

    def __init__(self, tournament, home=None, away=None):
        self.uuid = uuid.uuid4()
        self.tournament = tournament
        self.home = home
        self.away = away
        self.winner = None
        #: One of WAITING, PENDING, STARTED, COMPLETED, etc
        self.state = None

    @property
    def active(self):
        """ True if both players are assigned and the match isn't complete """
        return self.home is not None and self.away is not None and self.winner is None

    @property
    def is_complete(self):
        """ True if the winner has been assigned """
        return self.winner is not None

    def report_result(self, winner):
        """ winner == Match.TIE to report a tie """
        self.winner = winner
        if winner == Match.TIE:
            self.loser = Match.TIE
        elif winner == self.home:
            self.loser = self.away
        else:
            self.loser = self.home
        self.tournament.handle_match_result(self)

    def __repr__(self):
        return str(self)

    def __str__(self):
        return "Home: {} / Away: {} / Result: {}".format(self.home, self.away, self.winner)


class CallbackMixin(object):
    def __init__(self):
        self._callbacks = dict()

    def add_callback(self, event, handler):
        self._callbacks.setdefault(event, []).append(handler)

    def trigger_event(self, event, *args, **kwargs):
        for handler in self._callbacks.get(event, []):
            handler(self, *args, **kwargs)


class Tournament(CallbackMixin):
    """ Events:
            on_full(tournament) - triggered when tournament fills up
            on_start(tournament) - triggers when tournament is started
            on_complete(tournament) - triggers when all matches are completed
            on_match_ready(tournament, match) - triggers when match players are determined
            on_match_complete(tournament, match) - triggers when match results are reported
    """
    def __init__(self, max_size=None, participants=None):
        super(Tournament, self).__init__()
        self.matches = list()
        self.participants = participants
        if participants is None:
            self.participants = list()

    def start(self):
        self.num_players = len(self.participants)
        self.order_players_by_initial_rank()
        for player in self.participants:
            player.tournament_score = 0

        self.trigger_event('on_start')
        self.seed_players()

    def handle_match_result(self, match):
        self.calc_match_points(match)
        self.trigger_event('on_match_complete', match)
        self.process_match_result(match)

    def calc_match_points(self, match):
        """ This is a hook for tournaments to update a player's tournament_score
            attribute based on the match results.
        """
        if match.winner == match.TIE:
            match.home.tournament_score += 1
            match.away.tournament_score += 1
        else:
            match.winner.tournament_score += 3
            match.loser.tournament_score += 0

    def get_players_by_rank(self):
        """ Orders players by their current tournament results
        """
        return sorted(self.participants, key=lambda p: p.tournament_score, reverse=True)

    @property
    def active_matches(self):
        return filter(lambda m: m.active, self.matches)

    @property
    def completed_matches(self):
        return filter(lambda m: m.is_complete, self.matches)

    def seed_players(self):
        """ This function seeds the players into the tournament right when it starts.
        """
        raise NotImplementedError()

    def order_players_by_initial_rank(self):
        """ Orders players in place for initial seeding.
            First players get the bys and get paired with the last players.

            Default behavior is to use the order they were added.
        """
        pass

    def process_match_result(self, match):
        """ This is a hook for tournaments to update and direct player progress
            through the tournament based on the results of the given match.

            This function must make a call to calc_match_points!
        """
        raise NotImplementedError()


class SwissTournament(Tournament):
    def __init__(self, rounds, max_size=None, participants=None):
        super(SwissTournament, self).__init__(max_size, participants)
        self.current_round = 0
        self.rounds = rounds
        self.opponents = dict()

    def seed_players(self):
        self.matches_per_round = len(self.participants) // 2
        self.setup_round()

    def setup_round(self):
        self.current_round += 1
        players = deque(self.get_players_by_rank())
        while players:
            # Players should play the highest ranked person that
            # they have not yet played (if possible).
            home = players.popleft()
            for player in players:
                if player not in self.opponents.setdefault(home, []):
                    away = player
                    players.remove(away)
                    break
            else:
                away = players.popleft()

            match = Match(self, home=home, away=away)
            home.set_current_match(match)
            away.set_current_match(match)
            self.opponents.setdefault(home, []).append(away)
            self.opponents.setdefault(away, []).append(home)
            self.matches.append(match)
            self.trigger_event('on_match_ready', match)
        self.trigger_event('on_start_round')

    def is_round_complete(self):
        return len(filter(lambda m: not m.is_complete, self.matches)) == 0

    def process_match_result(self, match):
        if self.is_round_complete():
            if self.current_round != self.rounds:
                self.setup_round()
            else:
                self.trigger_event('on_complete')
        else:
            pass  # Waiting for other players


class SingleEliminationTournament(Tournament):
    def __init__(self, max_size=None, participants=None):
        super(SingleEliminationTournament, self).__init__(max_size, participants)
        self.bracket = dict()
        self.sources = dict()

    def seed_players(self):
        self.rounds = int(math.ceil(math.log(self.num_players, 2)))
        self.field_size = 2 ** self.rounds

        # All initial matches are seeded by the players and bys
        match_queue = deque()
        player_queue = deque(self.participants)
        player_queue.extend([BY] * (self.field_size - self.num_players))
        while player_queue:
            # The 'best' players get the bys and play the 'worst' ones
            home = player_queue.popleft()
            away = player_queue.pop()
            home.score = 0
            away.score = 0
            match = Match(self, home=home, away=away)
            home.set_current_match(match)
            away.set_current_match(match)
            match_queue.append(match)
            self.trigger_event('on_match_ready', match)

        # All future matches go into our bracket so we know
        # how to process match results
        while len(match_queue) > 1:
            top = match_queue.popleft()
            bot = match_queue.popleft()
            match = Match(self)
            self.bracket[top] = match
            self.bracket[bot] = match
            self.sources[match] = (top, bot)
            match_queue.append(match)
            self.matches.append(top)
            self.matches.append(bot)

        # Don't forget the finals!
        self.matches.append(match_queue.pop())

        # Do all the necessary BY matches automatically
        # This works because matches are ordered by round already
        for match in self.matches:
            if match.away == BY:
                match.report_result(match.home)

    def process_match_result(self, match):
        if match not in self.bracket:
            # This is the end of the line for these players
            self.trigger_event('on_complete')
            return

        winner_match = self.bracket[match]
        match.winner.set_current_match(winner_match)
        home_source, away_source = self.sources[winner_match]
        if match == home_source:
            winner_match.home = match.winner
        else:
            winner_match.away = match.winner

        if winner_match.active:
            self.trigger_event('on_match_ready', winner_match)
