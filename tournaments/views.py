import json
import logging
logger = logging.getLogger(__name__)
from threading import Lock

from django.conf import settings
from django.contrib.auth import authenticate, login, get_user_model
User = get_user_model()
import django.contrib.messages as messages
from django.core import serializers
from django.core.urlresolvers import reverse_lazy
from django.views.generic.edit import FormView, CreateView

from draw.models import Debate, DebateTeam
from draw.models import TeamVenuePreference, InstitutionVenuePreference
from participants.models import Team, Institution
from utils.forms import SuperuserCreationForm
from utils.mixins import SuperuserRequiredMixin
from utils.views import *
from utils.misc import redirect_tournament
from venues.models import VenueGroup

from .forms import TournamentForm
from .models import Tournament, Division

@cache_page(10) # Set slower to show new indexes so it will show new pages
@tournament_view
def public_index(request, t):
    return render(request, 'public_tournament_index.html')

def index(request):
    tournaments = Tournament.objects.all()
    if tournaments.count() == 1:
        if request.user.is_authenticated():
            logger.debug('One tournament only, user is: %s, redirecting to tournament-admin-home', request.user)
            return redirect_tournament('tournament-admin-home', tournaments.first())
        else:
            logger.debug('One tournament only, user is: %s, redirecting to tournament-public-index', request.user)
            return redirect_tournament('tournament-public-index', tournaments.first())

    elif not tournaments.exists() and not User.objects.exists():
        logger.debug('No users and no tournaments, redirecting to blank-site-start')
        return redirect('blank-site-start')

    else:
        return render(request, 'site_index.html', dict(tournaments=tournaments))

@login_required
@tournament_view
def tournament_home(request, t):
    round = t.current_round
    # This should never happen, but if it does, fail semi-gracefully
    if round is None:
        if request.user.is_superuser:
            return HttpResponseBadRequest("You need to set the current round. <a href=\"/admin/tournaments/tournament\">Go to Django admin.</a>")
        else:
            raise Http404()

    context = {}

    context["round"] = round
    context["readthedocs_version"] = settings.READTHEDOCS_VERSION

    # If the tournament is blank, display a message on the page
    context["blank"] = not (t.team_set.exists() or t.adjudicator_set.exists() or t.venue_set.exists())

    # Draw Status
    draw = round.get_draw()
    context["total_ballots"] = draw.count()
    stats_none = draw.filter(result_status=Debate.STATUS_NONE).count()
    stats_draft = draw.filter(result_status=Debate.STATUS_DRAFT).count()
    stats_confirmed = draw.filter(result_status=Debate.STATUS_CONFIRMED).count()
    context["stats"] = [[0,stats_confirmed], [0,stats_draft], [0,stats_none]]

    return render(request, 'tournament_home.html', context)

@cache_page(settings.PUBLIC_PAGE_CACHE_TIMEOUT)
@public_optional_tournament_view('public_divisions')
def public_divisions(request, t):
    divisions = Division.objects.filter(tournament=t).all().select_related('venue_group')
    divisions = sorted(divisions, key=lambda x: x.name)
    venue_groups = set(d.venue_group for d in divisions)
    for uvg in venue_groups:
        uvg.divisions = [d for d in divisions if d.venue_group == uvg]

    return render(request, 'public_divisions.html', dict(venue_groups=venue_groups))

@cache_page(settings.PUBLIC_PAGE_CACHE_TIMEOUT)
@tournament_view
def all_tournaments_all_venues(request, t):
    venues = VenueGroup.objects.all()
    return render(request, 'public_all_tournament_venues.html', dict(venues=venues))

@cache_page(settings.PUBLIC_PAGE_CACHE_TIMEOUT)
@tournament_view
def all_draws_for_venue(request, t, venue_id):
    venue_group = VenueGroup.objects.get(pk=venue_id)
    debates = Debate.objects.filter(division__venue_group=venue_group).select_related(
        'round','round__tournament','division')
    return render(request, 'public_all_draws_for_venue.html', dict(
        venue_group=venue_group, debates=debates))


@tournament_view
def all_draws_for_institution(request, t, institution_id):
    # TODO: move to draws app
    institution = Institution.objects.get(pk=institution_id)
    debate_teams = DebateTeam.objects.filter(team__institution=institution).select_related(
        'debate', 'debate__division', 'debate__division__venue_group', 'debate__round')
    debates = [dt.debate for dt in debate_teams]

    return render(request, 'public_all_draws_for_institution.html', dict(
        institution=institution, debates=debates))



@admin_required
@round_view
def round_increment_check(request, round):
    if round != request.tournament.current_round: # doesn't make sense if not current round
        raise Http404()
    num_unconfirmed = round.get_draw().filter(result_status__in=[Debate.STATUS_NONE, Debate.STATUS_DRAFT]).count()
    increment_ok = num_unconfirmed == 0
    return render(request, "round_increment_check.html", dict(num_unconfirmed=num_unconfirmed, increment_ok=increment_ok))

@admin_required
@expect_post
@round_view
def round_increment(request, round):
    if round != request.tournament.current_round: # doesn't make sense if not current round
        raise Http404()
    request.tournament.advance_round()
    return redirect_round('draw', request.tournament.current_round )

@admin_required
@tournament_view
def division_allocations(request, t):
    teams = list(Team.objects.filter(tournament=t).all().values(
            'id', 'short_reference', 'division', 'use_institution_prefix', 'institution__code', 'institution__id'))

    for team in teams:
        team['institutional_preferences'] = list(
            InstitutionVenuePreference.objects.filter(
                institution=team['institution__id']).values(
                    'venue_group__short_name', 'priority', 'venue_group__id').order_by('-priority'))
        team['team_preferences'] = list(
            TeamVenuePreference.objects.filter(
                team=team['id']).values(
                    'venue_group__short_name', 'priority', 'venue_group__id').order_by('-priority'))

        # team['institutional_preferences'] = "test"
        # team['individual_preferences'] = "test"

    teams = json.dumps(teams)

    venue_groups = json.dumps(list(
        VenueGroup.objects.all().values(
            'id', 'short_name', 'team_capacity')))

    divisions = json.dumps(list(Division.objects.filter(tournament=t).all().values(
        'id', 'name', 'venue_group')))

    return render(request, "division_allocations.html", dict(
        teams=teams, divisions=divisions, venue_groups=venue_groups))

@admin_required
@tournament_view
def create_division(request, t):
    division = Division.objects.create(name="temporary_name", tournament=t)
    division.save()
    division.name = "%s" % division.id
    division.save()
    return redirect_tournament('division_allocations', t)

@admin_required
@tournament_view
def create_byes(request, t):
    return redirect_tournament('division_allocations', t)

@admin_required
@tournament_view
def create_division_allocation(request, t):
    from tournaments.division_allocator import DivisionAllocator

    teams = list(Team.objects.filter(tournament=t))
    institutions = Institution.objects.all()
    venue_groups = VenueGroup.objects.all()

    # Delete all existing divisions - this shouldn't affect teams (on_delete=models.SET_NULL))
    divisions = Division.objects.filter(tournament=t).delete()

    alloc = DivisionAllocator(teams=teams, divisions=divisions, venue_groups=venue_groups, tournament=t, institutions=institutions)
    success = alloc.allocate()

    if success:
        return redirect_tournament('division_allocations', t)
    else:
        return HttpResponseBadRequest("Couldn't create divisions")

@admin_required
@expect_post
@tournament_view
def set_division_venue_group(request, t):
    division = Division.objects.get(pk=int(request.POST['division']))
    if request.POST['venueGroup'] == '':
        division.venue_group = None
    else:
        division.venue_group = VenueGroup.objects.get(pk=int(request.POST['venueGroup']))

    print("saved venue group for for", division.name)
    division.save()
    return HttpResponse("ok")

@admin_required
@expect_post
@tournament_view
def set_team_division(request, t):
    team = Team.objects.get(pk=int(request.POST['team']))
    if request.POST['division'] == '':
        team.division = None;
    else:
        team.division = Division.objects.get(pk=int(request.POST['division']));

    print("saved divison for ", team.short_name)
    team.save()
    return HttpResponse("ok")




class BlankSiteStartView(FormView):
    """This view is presented to the user when there are no tournaments and no
    user accounts. It prompts the user to create a first superuser. It rejects
    all requests, GET or POST, if there exists any user account in the
    system."""

    form_class = SuperuserCreationForm
    template_name = "blank_site_start.html"
    lock = Lock()
    success_url = reverse_lazy('tabbycat-index')

    def get(self, request):
        if User.objects.exists():
            logger.error("Tried to get the blank-site-start view when a user account already exists.")
            return redirect('tabbycat-index')

        return super().get(request)

    def post(self, request):
        with self.lock:
            if User.objects.exists():
                logger.error("Tried to post the blank-site-start view when a user account already exists.")
                messages.error(request, "Whoops! It looks like someone's already created the first user account. Please log in.")
                return redirect('auth-login')

            return super().post(request)

    def form_valid(self, form):
        form.save()
        user = authenticate(username=self.request.POST['username'], password=self.request.POST['password1'])
        login(self.request, user)
        messages.success(self.request, "Welcome! You've created an account for %s." % user.username)

        return super().form_valid(form)

class CreateTournamentView(SuperuserRequiredMixin, CreateView):
    """This view allows a logged-in superuser to create a new tournament."""

    model = Tournament
    form_class = TournamentForm
    template_name = "create_tournament.html"
