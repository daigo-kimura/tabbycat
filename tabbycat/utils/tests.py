from contextlib import contextmanager
import json
import logging

from django.core.urlresolvers import reverse
from django.test import Client, modify_settings, override_settings, tag, TestCase
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities

from adjallocation.models import DebateAdjudicator
from adjfeedback.models import AdjudicatorFeedback
from draw.models import Debate, DebateTeam
from results.models import BallotSubmission
from results.result import VotingDebateResult
from tournaments.models import Tournament
from participants.models import Adjudicator, Institution, Speaker, Team
from venues.models import Venue

logger = logging.getLogger(__name__)


@contextmanager
def suppress_logs(name, level, returnto=logging.NOTSET):
    """Suppresses logging at or below `level` from the logger named `name` while
    in the context manager. The name of the logger must be provided, and as a
    matter of practice should be as specific as possible, to avoid overly
    suppressing logs.

    Usage:
        import logging
        from utils.tests import suppress_logs

        with suppress_logs('results.result', logging.WARNING): # or other level
            # test code
    """
    if '.' not in name and returnto == logging.NOTSET:
        logger.warning("Top-level modules (%s) should not be passed to suppress_logs", name)

    suppressed_logger = logging.getLogger(name)
    suppressed_logger.setLevel(level+1)
    yield
    suppressed_logger.setLevel(returnto)


class TournamentTestsMixin:
    """Mixin that provides methods for testing a populated view on a tournament,
    with a prepopulated database."""

    fixtures = ['completed_demo.json']
    round_seq = None

    def get_tournament(self):
        return Tournament.objects.first()

    def setUp(self):
        super().setUp()
        self.t = self.get_tournament()
        self.client = Client()

    def get_view_url(self, provided_view_name):
        return reverse(provided_view_name, kwargs=self.get_url_kwargs())

    def get_url_kwargs(self):
        t = self.get_tournament()
        kwargs = {'tournament_slug': t.slug}
        if self.round_seq is not None:
            kwargs['round_seq'] = self.round_seq
        return kwargs

    # Remove whitenoise middleware as it won't resolve on Travis
    @override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
    @modify_settings(MIDDLEWARE={'remove': ['whitenoise.middleware.WhiteNoiseMiddleware']})
    def get_response(self):
        return self.client.get(self.get_view_url(self.view_name), kwargs=self.get_url_kwargs())


class ConditionalTournamentTestsMixin(TournamentTestsMixin):
    """Mixin that provides tests for testing a view class that is conditionally
    shown depending on whether a user preference is set.

    Subclasses must inherit from TestCase separately. This can't be a TestCase
    subclass, because it provides tests which would be run on the base class."""

    view_toggle = None

    def validate_response(self, response):
        raise NotImplementedError

    def test_set_preference(self):
        # Check a page IS resolving when the preference is set
        self.t.preferences[self.view_toggle] = True
        response = self.get_response()

        # 200 OK should be issued if setting is not enabled
        self.assertEqual(response.status_code, 200)
        self.validate_response(response)

    def test_unset_preference(self):
        # Check a page is not resolving when the preference is not set
        self.t.preferences[self.view_toggle] = False

        with self.assertLogs('tournaments.mixins', logging.WARNING):
            response = self.get_response()

        # 302 redirect should be issued if setting is not enabled
        self.assertEqual(response.status_code, 302)


class ConditionalTournamentViewBasicCheckMixin(ConditionalTournamentTestsMixin):
    """Simply checks the view and only fails if an error is thrown"""

    def validate_response(self, response):
        return True


# Remove whitenoise middleware as it won't resolve on Travis
@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
@modify_settings(MIDDLEWARE={'remove': ['whitenoise.middleware.WhiteNoiseMiddleware']})
class TournamentTestCase(TournamentTestsMixin, TestCase):
    """Extension of django.test.TestCase that provides methods for testing a
    populated view on a tournament, with a prepopulated database.
    Selenium tests can't inherit from this otherwise fixtures wont be loaded;
    as per https://stackoverflow.com/questions/12041315/how-to-have-django-test-case-and-selenium-server-use-same-database"""
    pass


class TableViewTestsMixin:
    """Mixin that provides methods for validating data in table views.
    Subclasses should override the `table_data` methods."""

    # This can't be a TestCase subclass, because it is inherited by
    # ConditionalTableViewTestsMixin, which provides tests.

    def validate_response(self, response):
        self.validate_table_data(response)

    def validate_table_data(self, r):
        if 'tableData' in r.context and self.table_data():
            data = len(json.loads(r.context['tableData']))
            self.assertEqual(self.table_data(), data)

        if 'tableDataA' in r.context and self.table_data_a():
            data_a = len(json.loads(r.context['tableDataA']))
            self.assertEqual(self.table_data_a(), data_a)

        if 'tableDataB' in r.context and self.table_data_b():
            data_b = len(json.loads(r.context['tableDataB']))
            self.assertEqual(self.table_data_b(), data_b)

    def table_data(self):
        return False

    def table_data_a(self):
        return False

    def table_data_b(self):
        return False


class ConditionalTableViewTestsMixin(TableViewTestsMixin, ConditionalTournamentTestsMixin):
    """Combination of TableViewTestsMixin and ConditionalTournamentTestsMixin,
    for convenience."""


class BaseDebateTestCase(TestCase):
    """Currently used in availability and participants tests as a pseudo fixture
    to create the basic data to simulate simple tournament functions"""

    def setUp(self):
        super().setUp()
        # add test models
        self.t = Tournament.objects.create(slug="tournament")
        for i in range(4):
            ins = Institution.objects.create(code="INS%s" % i, name="Institution %s" % i)
            for j in range(3):
                t = Team.objects.create(tournament=self.t, institution=ins,
                         reference="Team%s%s" % (i, j))
                for k in range(2):
                    Speaker.objects.create(team=t, name="Speaker%s%s%s" % (i, j, k))
            for j in range(2):
                Adjudicator.objects.create(tournament=self.t, institution=ins,
                                           name="Adjudicator%s%s" % (i, j), test_score=0)

        for i in range(8):
            Venue.objects.create(name="Venue %s" % i, priority=i, tournament=self.t)
            Venue.objects.create(name="IVenue %s" % i, priority=i)

    def tearDown(self):
        DebateTeam.objects.all().delete()
        Institution.objects.all().delete()
        self.t.delete()


class FeedbackTestMixin:
    """Mixin that provides methods for creating a debate and a feedback.
    Subclasses must create data to `adjudicator`, `institution`, `teams`, `venues`
    and `round` in setUp() properly."""

    def _team(self, t):
        return Team.objects.get(tournament=self.t, reference=t)

    def _adj(self, a):
        return Adjudicator.objects.get(tournament=self.t, name=a)

    def _dt(self, debate, t):
        return DebateTeam.objects.get(debate=debate, team=self._team(t))

    def _da(self, debate, a):
        return DebateAdjudicator.objects.get(debate=debate, adjudicator=self._adj(a))

    def _create_debate(self, teams, adjs, votes, trainees=[], venue=None):
        """Enters a debate into the database, using the teams and adjudicators specified.
        `votes` should be a string (or iterable of characters) indicating "a" for affirmative or
            "n" for negative, e.g. "ann" if the chair was rolled in a decision for the negative.
        The method will give the winning team all 76s and the losing team all 74s.
        The first adjudicator is the chair; the rest are panellists."""

        if venue is None:
            venue = Venue.objects.first()
        debate = Debate.objects.create(round=self.rd, venue=venue)

        aff, neg = teams
        aff_team = self._team(aff)
        DebateTeam.objects.create(debate=debate, team=aff_team, side=DebateTeam.SIDE_AFF)
        neg_team = self._team(neg)
        DebateTeam.objects.create(debate=debate, team=neg_team, side=DebateTeam.SIDE_NEG)

        chair = self._adj(adjs[0])
        DebateAdjudicator.objects.create(debate=debate, adjudicator=chair,
                type=DebateAdjudicator.TYPE_CHAIR)
        for p in adjs[1:]:
            panellist = self._adj(p)
            DebateAdjudicator.objects.create(debate=debate, adjudicator=panellist,
                    type=DebateAdjudicator.TYPE_PANEL)
        for tr in trainees:
            trainee = self._adj(tr)
            DebateAdjudicator.objects.create(debate=debate, adjudicator=trainee,
                    type=DebateAdjudicator.TYPE_TRAINEE)

        ballotsub = BallotSubmission(debate=debate, submitter_type=BallotSubmission.SUBMITTER_TABROOM)
        result = VotingDebateResult(ballotsub)

        for t, side in zip(teams, ('aff', 'neg')):
            team = self._team(t)
            speakers = team.speaker_set.all()
            for pos, speaker in enumerate(speakers, start=1):
                result.set_speaker(side, pos, speaker)
                result.set_ghost(side, pos, False)
            result.set_speaker(side, 4, speakers[0])
            result.set_ghost(side, 4, False)

        for a, vote in zip(adjs, votes):
            adj = self._adj(a)
            if vote == 'a':
                sides = ('aff', 'neg')
            elif vote == 'n':
                sides = ('neg', 'aff')
            else:
                raise ValueError
            for side, score in zip(sides, (76, 74)):
                for pos in range(1, 4):
                    result.set_score(adj, side, pos, score)
                result.set_score(adj, side, 4, score / 2)

        ballotsub.confirmed = True
        ballotsub.save()
        result.save()

        return debate

    def _create_feedback(self, source, target):
        if isinstance(source, DebateTeam):
            source_kwargs = dict(source_team=source)
        else:
            source_kwargs = dict(source_adjudicator=source)
        target_adj = self._adj(target)
        return AdjudicatorFeedback.objects.create(confirmed=True, adjudicator=target_adj, score=3,
                **source_kwargs)


@tag('selenium') # Exclude from Travis
class SeleniumTestCase(StaticLiveServerTestCase):
    """Used to verify rendered html and javascript functionality on the site as
    rendered. Opens a Chrome window and checks for JS/DOM state on the fixture
    debate."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Capabilities provide access to JS console
        capabilities = DesiredCapabilities.CHROME
        capabilities['loggingPrefs'] = {'browser':'ALL'}
        cls.selenium = WebDriver(desired_capabilities=capabilities)
        cls.selenium.implicitly_wait(10)

    def test_no_js_errors(self):
        # Check console for errors; fail the test if so
        for entry in self.selenium.get_log('browser'):
            if entry['level'] == 'SEVERE':
                raise RuntimeError('Page loaded in selenium has a JS error')

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super().tearDownClass()


@override_settings(STATICFILES_STORAGE='django.contrib.staticfiles.storage.StaticFilesStorage')
@modify_settings(MIDDLEWARE={'remove': ['whitenoise.middleware.WhiteNoiseMiddleware']})
class SeleniumTournamentTestCase(TournamentTestsMixin, SeleniumTestCase):
    """ Basically reimplementing BaseTournamentTest; but use cls not self """

    set_preferences = None
    unset_preferences = None

    def setUp(self):
        super().setUp()
        if self.set_preferences:
            for pref in self.set_preferences:
                self.t.preferences[pref] = True
        if self.unset_preferences:
            for pref in self.unset_preferences:
                self.t.preferences[pref] = False
