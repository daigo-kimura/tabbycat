from django.test import TestCase

from draw.models import DebateTeam
from participants.models import Adjudicator, Institution, Speaker, Team
from tournaments.models import Round, Tournament
from utils.tests import FeedbackTestMixin
from venues.models import Venue


class TestFeedbackScore(FeedbackTestMixin, TestCase):

    NUM_TEAMS = 4
    NUM_ADJS = 4
    NUM_VENUES = 2
    NUM_ROUNDS = 2

    def setUp(self):
        self.t = Tournament.objects.create()
        for i in range(self.NUM_TEAMS):
            inst = Institution.objects.create(code=i, name=i)
            team = Team.objects.create(tournament=self.t, institution=inst, reference=i)
            for j in range(3):
                Speaker.objects.create(team=team, name="%d-%d" % (i, j))

        adjsinst = Institution.objects.create(code="Adjs", name="Adjudicators")
        for i in range(self.NUM_ADJS):
            Adjudicator.objects.create(tournament=self.t,
                                       institution=adjsinst,
                                       name=i, test_score=3)
        for i in range(self.NUM_VENUES):
            Venue.objects.create(name=i, priority=i)

        for i in range(self.NUM_ROUNDS):
            Round.objects.create(tournament=self.t,
                                 seq=i + 1,
                                 abbreviation="R%d" % i,
                                 feedback_weight=0.25,
                                 silent=True if i - 1 == self.NUM_ROUNDS else False)

    def tearDown(self):
        DebateTeam.objects.all().delete()
        Round.objects.all().delete()
        Institution.objects.all().delete()
        Venue.objects.all().delete()
        self.t.delete()

    def test_before_tournament(self):
        for i, rd in enumerate(Round.objects.order_by('seq').all()):
            feedback_weight = rd.feedback_weight
            for opt in ('macro', 'micro'):
                # TODO: avoid referencing to _prefs
                self.t._prefs['average_feedback_score_calculation'] = opt
                score_func = self.t.avg_feedback_score_func
                for a in Adjudicator.objects.all():
                    self.assertEqual(a.weighted_score(feedback_weight, score_func), 3)

    def test_after_round(self):
        self.rd = Round.objects.filter(seq=1).first()
        debate1 = self._create_debate((0, 1), (0, 1, 2), "aaa", venue=self._venue('0'))
        debate2 = self._create_debate((2, 3), (3,), "a", venue=self._venue('1'))
        self._create_feedback(self._da(debate1, 1), 0, score=2)
        self._create_feedback(self._da(debate1, 2), 0, score=2)
        self._create_feedback(self._dt(debate1, 0), 0, score=3)
        self._create_feedback(self._dt(debate1, 1), 0, score=3)
        self._create_feedback(self._dt(debate2, 2), 3, score=2)
        self._create_feedback(self._dt(debate2, 3), 3, score=3)

        for opt in ('macro', 'micro'):
            # TODO: avoid referencing to _prefs
            self.t._prefs['average_feedback_score_calculation'] = opt
            score_func = self.t.avg_feedback_score_func
            for a in Adjudicator.objects.all():
                final_score = a.weighted_score(self.rd.feedback_weight, score_func)
                if a.name in ['0', '3']:
                    self.assertEqual(final_score, 0.75 * 3 + 0.25 * 2.5)
                else:
                    self.assertEqual(final_score, 3)

        self.rd = Round.objects.filter(seq=2).first()
        debate1 = self._create_debate((0, 1), (0, 1, 2), "aaa", venue=self._venue('0'))
        debate2 = self._create_debate((2, 3), (3,), "a", venue=self._venue('1'))
        self._create_feedback(self._da(debate1, 1), 0, score=1)
        self._create_feedback(self._da(debate1, 2), 0, score=1)

        for opt in ('macro', 'micro'):
            # TODO: avoid referencing to _prefs
            self.t._prefs['average_feedback_score_calculation'] = opt
            score_func = self.t.avg_feedback_score_func
            for a in Adjudicator.objects.all():
                final_score = a.weighted_score(self.rd.feedback_weight, score_func)
                if a.name == '0':
                    if opt == 'macro':
                        self.assertEqual(final_score, 0.75 * 3 + 0.25 * 1.75)
                    elif opt == 'micro':
                        self.assertEqual(final_score, 0.75 * 3 + 0.25 * 2)
                elif a.name == '3':
                    self.assertEqual(final_score, 0.75 * 3 + 0.25 * 2.5)
                else:
                    self.assertEqual(final_score, 3)
