from django.conf.urls import url

from . import views

urlpatterns = [

    # Display
    url(r'^round/(?P<round_seq>\d+)/$',
        views.draw,
        name='draw'),
    url(r'^round/(?P<round_seq>\d+)/details/$',
        views.draw_with_standings,
        name='draw_with_standings'),
    url(r'^round/(?P<round_seq>\d+)/display_by_venue/$',
        views.draw_display_by_venue,
        name='draw_display_by_venue'),
    url(r'^round/(?P<round_seq>\d+)/display_by_team/$',
        views.draw_display_by_team,
        name='draw_display_by_team'),

    # Print
    url(r'^round/(?P<round_seq>\d+)/print/scoresheets/$',
        views.draw_print_scoresheets,
        name='draw_print_scoresheets'),
    url(r'^round/(?P<round_seq>\d+)/print/feedback/$',
        views.draw_print_feedback,
        name='draw_print_feedback'),
    url(r'^round/(?P<round_seq>\d+)/master_sheets/list/$',
        views.master_sheets_list,
        name='master_sheets_list'),
    url(r'^round/(?P<round_seq>\d+)/master_sheets/venue_group/(?P<venue_group_id>\d+)/$',
        views.master_sheets_view,
        name='master_sheets_view'),

    # Creation/Release
    url(r'^round/(?P<round_seq>\d+)/create/$',
        views.create_draw,
        name='create_draw'),
    url(r'^round/(?P<round_seq>\d+)/confirm/$',
        views.confirm_draw,
        name='confirm_draw'),
    url(r'^round/(?P<round_seq>\d+)/release/$',
        views.release_draw,
        name='release_draw'),
    url(r'^round/(?P<round_seq>\d+)/unrelease/$',
        views.unrelease_draw,
        name='unrelease_draw'),
    url(r'^round/(?P<round_seq>\d+)/start_time/set/$',
        views.set_round_start_time,
        name='set_round_start_time'),

    # Side Editing
    url(r'^side_allocations/$',
        views.side_allocations,
        name='side_allocations'),
    url(r'^round/(?P<round_seq>\d+)/matchups/edit/$',
        views.draw_matchups_edit,
        name='draw_matchups_edit'),
    url(r'^round/(?P<round_seq>\d+)/matchups/save/$',
        views.save_matchups,
        name='save_matchups'),

    # Venue Editing
    url(r'^round/(?P<round_seq>\d+)/venues/$',
        views.draw_venues_edit,
        name='draw_venues_edit'),
    url(r'^round/(?P<round_seq>\d+)/venues/save/$',
        views.save_venues,
        name='save_venues'),
]