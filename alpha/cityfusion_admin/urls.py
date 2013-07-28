from django.conf.urls.defaults import patterns, url
from cityfusion_admin import views

urlpatterns = patterns('',
    url(r'^report-event/$', 
        views.report_event,
        name='report_event'
    ),
    url(r'^claim-event/$',
        views.claim_event,
        name='claim_event'
    ),

    url(r'^report-event-list/$', 
        views.report_event_list,
        name='report_event_list'
    ),
    url(r'^report-event-process/(?P<report_id>\d+)/$', 
        views.report_event_process,
        name='report_event_process'
    ),
    url(r'^claim-event-list/$',
        views.claim_event_list,
        name='claim_event_list'
    ),
    url(r'^transfer-event/(?P<claim_id>\d+)/$',
        views.transfer_event,
        name='transfer_event'
    ),
    url(r'^claim-event-refuse/(?P<claim_id>\d+)/$', 
        views.claim_event_refuse,
        name='claim_event_refuse'
    ),
)
