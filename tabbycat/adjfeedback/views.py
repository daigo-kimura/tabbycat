import json
import logging
import math

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.translation import ungettext
from django.views.generic.base import TemplateView, View
from django.views.generic.edit import FormView

from actionlog.mixins import LogActionMixin
from actionlog.models import ActionLogEntry
from participants.models import Adjudicator, Team
from participants.prefetch import populate_feedback_scores
from results.mixins import PublicSubmissionFieldsMixin, TabroomSubmissionFieldsMixin
from tournaments.mixins import (PublicTournamentPageMixin, SingleObjectByRandomisedUrlMixin,
                                SingleObjectFromTournamentMixin, TournamentMixin)

from utils.misc import reverse_tournament
from utils.mixins import (CacheMixin, SuperuserOrTabroomAssistantTemplateResponseMixin,
                          SuperuserRequiredMixin)
from utils.views import JsonDataResponseView, PostOnlyRedirectView, VueTableTemplateView
from utils.tables import TabbycatTableBuilder

from .models import AdjudicatorFeedback, AdjudicatorTestScoreHistory
from .forms import make_feedback_form_class
from .tables import FeedbackTableBuilder
from .utils import get_feedback_overview, parse_feedback
from .progress import get_feedback_progress

logger = logging.getLogger(__name__)


class GetAdjScores(LoginRequiredMixin, TournamentMixin, JsonDataResponseView):

    def get_data(self):
        t = self.get_tournament()
        feedback_weight = t.current_round.feedback_weight
        score_func = t.avg_feedback_score_func
        data = {}
        for adj in Adjudicator.objects.all():
            data[adj.id] = adj.weighted_score(feedback_weight, score_func)
        return data


class GetAdjFeedbackJSON(LoginRequiredMixin, TournamentMixin, JsonDataResponseView):

    def get_data(self):
        adjudicator = get_object_or_404(Adjudicator, pk=self.kwargs['pk'])
        feedback = adjudicator.get_feedback().filter(confirmed=True)
        questions = self.get_tournament().adj_feedback_questions
        data = [parse_feedback(f, questions) for f in feedback]
        return data


class BaseFeedbackOverview(TournamentMixin, VueTableTemplateView):
    """ Also inherited by the adjudicator's tab """

    def get_adjudicators(self):
        t = self.get_tournament()
        if t.pref('share_adjs'):
            return Adjudicator.objects.filter(Q(tournament=t) | Q(tournament__isnull=True))
        else:
            return Adjudicator.objects.filter(tournament=t)

    def get_context_data(self, **kwargs):
        t = self.get_tournament()
        adjudicators = self.get_adjudicators()
        weight = t.current_round.feedback_weight
        score_func = t.avg_feedback_score_func
        scores = [a.weighted_score(weight, score_func) for a in adjudicators]

        kwargs['c_breaking'] = adjudicators.filter(breaking=True).count()

        ntotal = len(scores)
        nchairs = t.team_set.count() // (4 if t.pref('teams_in_debate') == 'bp' else 2)
        ntrainees = [x < t.pref('adj_min_voting_score') for x in scores].count(True)
        npanellists = ntotal - nchairs - ntrainees

        max_score = int(math.ceil(t.pref('adj_max_score')))
        min_score = int(math.floor(t.pref('adj_min_score')))
        range_width = max_score - min_score
        band_widths = [range_width // 5] * 5
        for i in range(range_width - sum(band_widths)):
            band_widths[i] += 1
        band_widths = [x for x in band_widths if x > 0]
        bands = []
        threshold = max_score
        for width in band_widths:
            bands.append((threshold - width, threshold))
            threshold = threshold - width
        if not threshold == min_score:
            logger.error("Feedback bands calculation didn't work")

        band_specs = []
        threshold_classes = ['80', '70', '60', '50', '40'] # CSS suffix
        for (band_min, band_max), threshold_class in zip(bands, threshold_classes):
            band_specs.append({
                'min': band_min, 'max': band_max, 'class': threshold_class,
                'count': [x >= band_min and x < band_max for x in scores].count(True)
            })
        band_specs[0]['count'] += [x == max_score for x in scores].count(True)

        noutside_range = [x < min_score or x > max_score for x in scores].count(True)

        kwargs.update({
            'c_total': ntotal,
            'c_chairs': nchairs,
            'c_panellists': npanellists,
            'c_trainees': ntrainees,
            'c_thresholds': band_specs,
            'nadjs_outside_range': noutside_range,
            'test_percent': (1.0 - weight) * 100,
            'feedback_percent': weight * 100,
        })

        return super().get_context_data(**kwargs)

    def get_table(self):
        t = self.get_tournament()
        adjudicators = self.get_adjudicators()
        populate_feedback_scores(adjudicators)
        # Gather stats necessary to construct the graphs
        adjudicators = get_feedback_overview(t, adjudicators)
        table = FeedbackTableBuilder(view=self, sort_key=self.sort_key,
                                     sort_order=self.sort_order)
        table = self.annotate_table(table, adjudicators)
        return table


class FeedbackOverview(LoginRequiredMixin, BaseFeedbackOverview):

    page_title = 'Feedback Overview'
    page_emoji = '🙅'
    for_public = False
    sort_key = 'Score'
    sort_order = 'desc'
    template_name = 'feedback_overview.html'

    def annotate_table(self, table, adjudicators):
        table.add_adjudicator_columns(adjudicators, hide_institution=True, subtext='institution')
        table.add_breaking_checkbox(adjudicators)
        table.add_weighted_score_columns(adjudicators)
        table.add_test_score_columns(adjudicators, editable=True)
        table.add_feedback_graphs(adjudicators)
        table.add_feedback_link_columns(adjudicators)
        table.add_feedback_misc_columns(adjudicators)
        return table


class FeedbackByTargetView(LoginRequiredMixin, TournamentMixin, VueTableTemplateView):
    template_name = "feedback_base.html"
    page_title = 'Find Feedback on Adjudicator'
    page_emoji = '🔍'

    def get_table(self):
        tournament = self.get_tournament()
        table = TabbycatTableBuilder(view=self, sort_key="Name")
        table.add_adjudicator_columns(tournament.adjudicator_set.all())
        feedback_data = []
        for adj in tournament.adjudicator_set.all():
            count = adj.adjudicatorfeedback_set.count()
            feedback_data.append({
                'text': ungettext("%(count)d feedback", "%(count)d feedbacks", count) % {'count': count},
                'link': reverse_tournament('adjfeedback-view-on-adjudicator', tournament, kwargs={'pk': adj.id}),
            })
        table.add_column("Feedbacks", feedback_data)
        return table


class FeedbackBySourceView(LoginRequiredMixin, TournamentMixin, VueTableTemplateView):

    template_name = "feedback_base.html"
    page_title = 'Find Feedback'
    page_emoji = '🔍'

    def get_tables(self):
        tournament = self.get_tournament()

        teams = tournament.team_set.all()
        team_table = TabbycatTableBuilder(
            view=self, title='From Teams', sort_key='Team')
        team_table.add_team_columns(teams)
        team_feedback_data = []
        for team in teams:
            count = AdjudicatorFeedback.objects.filter(
                source_team__team=team).select_related(
                'source_team__team').count()
            team_feedback_data.append({
                'text': ungettext("%(count)d feedback", "%(count)d feedbacks", count) % {'count': count},
                'link': reverse_tournament('adjfeedback-view-from-team',
                                           tournament,
                                           kwargs={'pk': team.id}),
            })
        team_table.add_column("Feedbacks", team_feedback_data)

        adjs = tournament.adjudicator_set.all()
        adj_table = TabbycatTableBuilder(
            view=self, title='From Adjudicators', sort_key='Name')
        adj_table.add_adjudicator_columns(adjs)
        adj_feedback_data = []
        for adj in adjs:
            count = AdjudicatorFeedback.objects.filter(
                source_adjudicator__adjudicator=adj).select_related(
                'source_adjudicator__adjudicator').count()
            adj_feedback_data.append({
                'text': ungettext("%(count)d feedback", "%(count)d feedbacks", count) % {'count': count},
                'link': reverse_tournament('adjfeedback-view-from-adjudicator',
                                           tournament,
                                           kwargs={'pk': adj.id}),
            })
        adj_table.add_column("Feedbacks", adj_feedback_data)

        return [team_table, adj_table]


class FeedbackCardsView(LoginRequiredMixin, TournamentMixin, TemplateView):
    """Base class for views displaying feedback as cards."""

    def get_score_thresholds(self):
        tournament = self.get_tournament()
        min_score = tournament.pref('adj_min_score')
        max_score = tournament.pref('adj_max_score')
        score_range = max_score - min_score
        return {
            'low_score'     : min_score + score_range / 10,
            'medium_score'  : min_score + score_range / 5,
            'high_score'    : max_score - score_range / 10,
        }

    def get_feedbacks(self):
        questions = self.get_tournament().adj_feedback_questions
        feedbacks = self.get_feedback_queryset()
        for feedback in feedbacks:
            feedback.items = []
            for question in questions:
                try:
                    answer = question.answer_set.get(feedback=feedback).answer
                except ObjectDoesNotExist:
                    continue
                feedback.items.append({'question': question, 'answer': answer})
        return feedbacks

    def get_feedback_queryset(self):
        raise NotImplementedError()

    def get_context_data(self, **kwargs):
        kwargs['feedbacks'] = self.get_feedbacks()
        kwargs['score_thresholds'] = self.get_score_thresholds()
        return super().get_context_data(**kwargs)


class LatestFeedbackView(FeedbackCardsView):
    """View displaying the latest feedback."""

    template_name = "feedback_latest.html"

    def get_feedback_queryset(self):
        t = self.get_tournament()
        return AdjudicatorFeedback.objects.filter(
            Q(adjudicator__tournament=t) |
            Q(adjudicator__tournament__isnull=True)).order_by(
            '-timestamp')[:30].select_related(
            'adjudicator', 'source_adjudicator__adjudicator', 'source_team__team')


class FeedbackFromSourceView(SingleObjectFromTournamentMixin, FeedbackCardsView):
    """Base class for views displaying feedback from a given team or adjudicator."""

    template_name = "feedback_by_source.html"
    source_name_attr = None
    source_type = "from"
    adjfeedback_filter_field = None

    def get_context_data(self, **kwargs):
        kwargs['source_name'] = getattr(self.object, self.source_name_attr, '<ERROR>')
        kwargs['source_type'] = self.source_type
        return super().get_context_data(**kwargs)

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def get_feedback_queryset(self):
        kwargs = {self.adjfeedback_filter_field: self.object}
        return AdjudicatorFeedback.objects.filter(**kwargs).order_by('-timestamp')


class FeedbackOnAdjudicatorView(FeedbackFromSourceView):
    """Base class for views displaying feedback from a given team or adjudicator."""

    model = Adjudicator
    source_name_attr = 'name'
    source_type = "on"
    adjfeedback_filter_field = 'adjudicator'
    allow_null_tournament = True


class FeedbackFromTeamView(FeedbackFromSourceView):
    """View displaying feedback from a given source."""
    model = Team
    source_name_attr = 'short_name'
    adjfeedback_filter_field = 'source_team__team'
    allow_null_tournament = False


class FeedbackFromAdjudicatorView(FeedbackFromSourceView):
    """View displaying feedback from a given adjudicator."""
    model = Adjudicator
    source_name_attr = 'name'
    adjfeedback_filter_field = 'source_adjudicator__adjudicator'
    allow_null_tournament = True


class GetAdjFeedback(LoginRequiredMixin, TournamentMixin, JsonDataResponseView):

    def parse_feedback(self, f, questions):

        if f.source_team:
            source_annotation = " (" + f.source_team.get_result_display() + ")"
        elif f.source_adjudicator:
            source_annotation = " (" + f.source_adjudicator.get_type_display() + ")"
        else:
            source_annotation = ""

        data = [
            str(f.round.abbreviation),
            str(str(f.version) + (f.confirmed and "*" or "")),
            f.debate.bracket,
            f.debate.matchup,
            str(str(f.source) + source_annotation),
            f.score,
        ]
        for question in questions:
            try:
                data.append(question.answer_set.get(feedback=f).answer)
            except ObjectDoesNotExist:
                data.append("-")
        data.append(f.confirmed)
        return data

    def get_data(self):
        t = self.get_tournament()
        adj = get_object_or_404(Adjudicator, pk=int(self.request.GET['id']))
        feedback = adj.get_feedback().filter(confirmed=True)
        questions = t.adj_feedback_questions

        data = [self.parse_feedback(f, questions) for f in feedback]
        data = [parse_feedback(f, questions) for f in feedback]
        return {'aaData': data}


class BaseAddFeedbackIndexView(TournamentMixin, TemplateView):

    def get_context_data(self, **kwargs):
        tournament = self.get_tournament()
        if not tournament.pref('share_adjs'):
            kwargs['adjudicators'] = tournament.adjudicator_set.all().order_by('name')
        else:
            Adjudicator.objects.all().order_by('name')

        kwargs['teams'] = tournament.team_set.all()
        return super().get_context_data(**kwargs)


class TabroomAddFeedbackIndexView(SuperuserOrTabroomAssistantTemplateResponseMixin, BaseAddFeedbackIndexView):
    """View for the index page for tabroom officials to add feedback. The index
    page lists all possible sources; officials should then choose the author
    of the feedback."""

    superuser_template_name = 'add_feedback.html'
    assistant_template_name = 'assistant_add_feedback.html'


class PublicAddFeedbackIndexView(CacheMixin, PublicTournamentPageMixin, BaseAddFeedbackIndexView):
    """View for the index page for public users to add feedback. The index page
    lists all possible sources; public users should then choose themselves."""

    template_name = 'public_add_feedback.html'

    def is_page_enabled(self, tournament):
        return tournament.pref('participant_feedback') == 'public'


class BaseAddFeedbackView(LogActionMixin, SingleObjectFromTournamentMixin, FormView):
    """Base class for views that allow users to add feedback."""

    template_name = "enter_feedback.html"
    pk_url_kwarg = 'source_id'
    allow_null_tournament = True
    action_log_content_object_attr = 'adj_feedback'

    def get_form_class(self):
        return make_feedback_form_class(self.object, self.get_tournament(),
                self.get_submitter_fields(), **self.feedback_form_class_kwargs)

    def form_valid(self, form):
        self.adj_feedback = form.save()
        self.round = self.adj_feedback.debate.round  # for LogActionMixin
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        source = self.object
        if isinstance(source, Adjudicator):
            kwargs['source_type'] = "adj"
        elif isinstance(source, Team):
            kwargs['source_type'] = "team"
        kwargs['source_name'] = self.source_name
        return super().get_context_data(**kwargs)

    def _populate_source(self):
        self.object = self.get_object()  # For compatibility with SingleObjectMixin
        if isinstance(self.object, Adjudicator):
            self.source_name = self.object.name
        elif isinstance(self.object, Team):
            self.source_name = self.object.short_name
        else:
            self.source_name = "<ERROR>"

    def get(self, request, *args, **kwargs):
        self._populate_source()
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self._populate_source()
        return super().post(request, *args, **kwargs)


class TabroomAddFeedbackView(TabroomSubmissionFieldsMixin, LoginRequiredMixin, BaseAddFeedbackView):
    """View for tabroom officials to add feedback."""

    action_log_type = ActionLogEntry.ACTION_TYPE_FEEDBACK_SAVE
    feedback_form_class_kwargs = {
        'confirm_on_submit': True,
        'enforce_required': False,
        'include_unreleased_draws': True,
        'use_tournament_password': False,
    }

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, "Feedback from {} on {} added.".format(
            self.source_name, self.adj_feedback.adjudicator.name))
        return result

    def get_success_url(self):
        return reverse_tournament('adjfeedback-add-index', self.get_tournament())


class PublicAddFeedbackView(PublicSubmissionFieldsMixin, PublicTournamentPageMixin, BaseAddFeedbackView):
    """Base class for views for public users to add feedback."""

    action_log_type = ActionLogEntry.ACTION_TYPE_FEEDBACK_SUBMIT
    feedback_form_class_kwargs = {
        'confirm_on_submit': True,
        'enforce_required': True,
        'include_unreleased_draws': False,
        'use_tournament_password': True,
    }

    def form_valid(self, form):
        result = super().form_valid(form)
        messages.success(self.request, "Thanks, {}! Your feedback on {} has been recorded.".format(
            self.source_name, self.adj_feedback.adjudicator.name))
        return result


class PublicAddFeedbackByRandomisedUrlView(SingleObjectByRandomisedUrlMixin, PublicAddFeedbackView):
    """View for public users to add feedback, where the URL is a randomised one."""

    def is_page_enabled(self, tournament):
        return tournament.pref('participant_feedback') == 'private-urls'

    def get_success_url(self):
        # Redirect to non-cached page: their original private URL
        if isinstance(self.object, Adjudicator):
            return reverse_tournament('adjfeedback-public-add-from-adjudicator-randomised',
                self.get_tournament(), kwargs={'url_key': self.object.url_key})
        elif isinstance(self.object, Team):
            return reverse_tournament('adjfeedback-public-add-from-team-randomised',
                self.get_tournament(), kwargs={'url_key': self.object.url_key})
        else:
            raise ValueError("Private feedback source is not of a valid type")


class PublicAddFeedbackByIdUrlView(PublicAddFeedbackView):
    """View for public users to add feedback, where the URL is by object ID."""

    def is_page_enabled(self, tournament):
        return tournament.pref('participant_feedback') == 'public'

    def get_success_url(self):
        # Redirect to non-cached page: the public feedback form
        if isinstance(self.object, Adjudicator):
            return reverse_tournament('adjfeedback-public-add-from-adjudicator-pk',
                self.get_tournament(), kwargs={'source_id': self.object.id})
        elif isinstance(self.object, Team):
            return reverse_tournament('adjfeedback-public-add-from-team-pk',
                self.get_tournament(), kwargs={'source_id': self.object.id})
        else:
            raise ValueError("Public feedback source is not of a valid type")


class AdjudicatorActionError(RuntimeError):
    pass


class BaseAdjudicatorActionView(LogActionMixin, SuperuserRequiredMixin, TournamentMixin, PostOnlyRedirectView):

    tournament_redirect_pattern_name = 'adjfeedback-overview'
    action_log_content_object_attr = 'adjudicator'

    def get_adjudicator(self, request):
        try:
            adj_id = int(request.POST["adj_id"])
            adjudicator = Adjudicator.objects.get(id=adj_id)
        except (ValueError, Adjudicator.DoesNotExist, Adjudicator.MultipleObjectsReturned):
            raise AdjudicatorActionError("Whoops! I didn't recognise that adjudicator: {}".format(adj_id))
        return adjudicator

    def post(self, request, *args, **kwargs):
        try:
            self.adjudicator = self.get_adjudicator(request)
            self.modify_adjudicator(request, self.adjudicator)
            self.log_action()  # Need to call explicitly, since this isn't a form view
        except AdjudicatorActionError as e:
            messages.error(request, str(e))

        return super().post(request, *args, **kwargs)


class SetAdjudicatorTestScoreView(BaseAdjudicatorActionView):

    action_log_type = ActionLogEntry.ACTION_TYPE_TEST_SCORE_EDIT
    action_log_content_object_attr = 'atsh'

    def modify_adjudicator(self, request, adjudicator):
        try:
            score = float(request.POST["test_score"])
        except ValueError:
            raise AdjudicatorActionError("Whoops! The value isn't a valid test score.")

        adjudicator.test_score = score
        adjudicator.save()

        atsh = AdjudicatorTestScoreHistory(
            adjudicator=adjudicator, round=self.get_tournament().current_round,
            score=score)
        atsh.save()
        self.atsh = atsh


class SetAdjudicatorBreakingStatusView(SuperuserRequiredMixin, TournamentMixin, LogActionMixin, View):

    action_log_type = ActionLogEntry.ACTION_TYPE_ADJUDICATOR_BREAK_SET

    def post(self, request, *args, **kwargs):
        body = self.request.body.decode('utf-8')
        posted_info = json.loads(body)
        adjudicator = Adjudicator.objects.get(id=posted_info['id'])
        adjudicator.breaking = posted_info['breaking']
        adjudicator.save()
        return JsonResponse(json.dumps(True), safe=False)


class SetAdjudicatorNoteView(BaseAdjudicatorActionView):

    action_log_type = ActionLogEntry.ACTION_TYPE_ADJUDICATOR_NOTE_SET

    def modify_adjudicator(self, request, adjudicator):
        try:
            note = str(request.POST["note"])
        except ValueError as e:
            raise AdjudicatorActionError("Whoop! There was an error interpreting that string: " + str(e))

        adjudicator.notes = note
        adjudicator.save()


class BaseFeedbackProgressView(TournamentMixin, VueTableTemplateView):

    page_title = 'Feedback Progress'
    page_subtitle = ''
    page_emoji = '🆘'

    def get_feedback_progress(self):
        if not hasattr(self, "_feedback_progress_result"):
            self._feedback_progress_result = get_feedback_progress(self.get_tournament())
        return self._feedback_progress_result

    def get_page_subtitle(self):
        teams_progress, adjs_progress = self.get_feedback_progress()
        total_missing = sum([progress.num_unsubmitted() for progress in teams_progress + adjs_progress])
        return "{:d} missing feedback submissions".format(total_missing)

    def get_tables(self):
        teams_progress, adjs_progress = self.get_feedback_progress()

        adjs_table = FeedbackTableBuilder(view=self, title="From Adjudicators",
            sort_key="Owed", sort_order="desc")
        adjudicators = [progress.adjudicator for progress in adjs_progress]
        adjs_table.add_adjudicator_columns(adjudicators, hide_metadata=True)
        adjs_table.add_feedback_progress_columns(adjs_progress)

        teams_table = FeedbackTableBuilder(view=self, title="From Teams",
            sort_key="Owed", sort_order="desc")
        teams = [progress.team for progress in teams_progress]
        teams_table.add_team_columns(teams)
        teams_table.add_feedback_progress_columns(teams_progress)

        return [adjs_table, teams_table]


class FeedbackProgress(SuperuserRequiredMixin, BaseFeedbackProgressView):
    template_name = 'feedback_base.html'


class PublicFeedbackProgress(PublicTournamentPageMixin, CacheMixin, BaseFeedbackProgressView):
    public_page_preference = 'feedback_progress'
