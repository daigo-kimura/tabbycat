from django.conf.urls import *

from . import views

urlpatterns = [
    # Viewing
    url(r'^$',
        views.public_results_index,
        name='public_results_index'),
    url(r'^round/(?P<round_seq>\d+)/$',
        views.public_results,
        name='public_results'),
    url(r'^ballots/debate/(?P<debate_id>\d+)/$',
        views.public_ballots_view,
        name='public_ballots_view'),

    # Ballots
    url(r'^add/$',
        views.public_ballot_submit,
        name='public_ballot_submit'),
    url(r'^add/adjudicator/(?P<adj_id>\d+)/$',
        views.public_new_ballotset_id,
        name='public_new_ballotset'),
    url(r'^add/a(?P<url_key>\w+)/$',
        views.public_new_ballotset_key,
        name='public_new_ballotset_key'),
]