from django.urls import include, path

from . import views

urlpatterns = [
    path('round/<int:round_seq>/', include([
        path('edit/',
            views.EditMotionsView.as_view(),
            name='motions-edit'),
        path('assign/',
            views.AssignMotionsView.as_view(),
            name='motions_assign'),
        path('release/',
            views.ReleaseMotionsView.as_view(),
            name='motions-release'),
        path('unrelease/',
            views.UnreleaseMotionsView.as_view(),
            name='motions-unrelease'),
        path('display/',
            views.DisplayMotionsView.as_view(),
            name='motions-display'),
    ])),
]
