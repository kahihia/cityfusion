from django.core.urlresolvers import reverse
from django.core.exceptions import ObjectDoesNotExist
from django.core.mail.message import EmailMessage
from django.utils.safestring import mark_safe

from django.http import HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template.loader import render_to_string
from django.template import RequestContext

from event import EVENTS_PER_PAGE, DEFAULT_FROM_EMAIL
from event.models import Event, picture_file_path
from event.forms import generate_form
from event.utils import TagInfo, EventSet
from django.http import Http404
from taggit.models import Tag
from django.conf import settings

import datetime

import re

def redirect(request):
    return HttpResponseRedirect( reverse('event_browse'))

def browse(request, old_tags=u'all', date=u'flow', num=1):
    pages = 0 # used in date filter code for determining if we have pagination
    num = int(num) -1 # see comment labeled NUMCODE
    today = datetime.datetime(*(datetime.date.today().timetuple()[:6])) # isnt python so easy to read?

    split_tags = []
    #parsing the tags string
    if old_tags != u'all':
        split_tags = old_tags.split(',')
        # Right now we query based on tags, and then later split this up based on date.
        # Does django make a query every time? If so this could be an expensive, inefficient way of
        # doing the job.
        upcoming_events = Event.events.filter(start_time__gte=today, tags__slug__in=split_tags).distinct()
    else:
        upcoming_events = Event.events.filter(start_time__gte=today)

    #now we filter based on the date selected
    # Sam note: I realize that i have way too many queries here, but im not really sure how
    # to combine them properly and still get the header correct. Levi mentioned having more
    # than one day listing per page, so they flow into one another, if that is the case then
    # there will have to be a number of different queries.
    # its possible I could try implementing this using loops, but I am afraid of what kind
    # of bugs might crop up if I had a database query in a loop - so i'm not going there.
    # IF django is lazy about the queries, then I'm totally saved here. And I think it is lazy.
    event_sets = []

    # error checking for num argument
    if int(num) < 0:
        num = 0

    # I should really combine this all into a function... there's a lot of shared code here
    if date == u'today':
        start = today
        end = today.replace(hour=23, minute=59, second=59)
        todays_events = upcoming_events.filter(
            start_time__year=today.year, 
            start_time__month=today.month,
            start_time__day=today.day)   
        pages = todays_events.count() / EVENTS_PER_PAGE
        todays_events = todays_events.order_by('start_time')[int(num)*EVENTS_PER_PAGE:EVENTS_PER_PAGE]
        event_sets.append( EventSet(u"Today's Events", todays_events ) )
    elif date == u'tomorrow':
        tomorrow = today + datetime.timedelta(days=1)
        start = tomorrow
        end = tomorrow.replace(hour=23, minute=59, second=59)
        tomorrows_events = upcoming_events.filter(start_time__year=tomorrow.year, 
                                                 start_time__month=tomorrow.month,
                                                 start_time__day=tomorrow.day)
        pages = tomorrows_events.count() / EVENTS_PER_PAGE
        tomorrows_events = tomorrows_events.order_by('start_time')[int(num)*EVENTS_PER_PAGE:int(num)*EVENTS_PER_PAGE + EVENTS_PER_PAGE]
        event_sets.append( EventSet(u"Tomorrow's Events", tomorrows_events ) )
    elif date == u'this-weekend':
        #weekday 6 5 4 sun sat fri
        end = today + datetime.timedelta(days=6-today.weekday())
        end = end.replace(hour=23,minute=59,second=59,microsecond=0)
        #sat is 5
        if today.weekday() == 5:
            start = today + datetime.timedelta(days=5-today.weekday())
            start = start.replace(hour=0,minute=0,second=0,microsecond=0)
        #friday at 5pm is the weekend.
        else:
            start = today + datetime.timedelta(days=4-today.weekday())
            start = start.replace(hour=17,minute=0,second=0,microsecond=0)
        this_weekends_events = upcoming_events.filter(start_time__range=(start,end))
        pages = this_weekends_events.count() / EVENTS_PER_PAGE
        this_weekends_events = this_weekends_events.order_by('start_time')[int(num)*EVENTS_PER_PAGE:int(num)*EVENTS_PER_PAGE + EVENTS_PER_PAGE]
        event_sets.append( EventSet(u'Events This Weekend', this_weekends_events) )
    elif date == u'this-week':
        end = today + datetime.timedelta(days=6-today.weekday())
        start = today
        this_weeks_events = upcoming_events.filter(start_time__range=(start,end))
        pages = this_weeks_events.count() / EVENTS_PER_PAGE
        this_weeks_events = this_weeks_events.order_by('start_time')[int(num)*EVENTS_PER_PAGE:int(num)*EVENTS_PER_PAGE + EVENTS_PER_PAGE]
        event_sets.append( EventSet(u'Events This Week', this_weeks_events ) )
    elif date == u'next-week':
        end = today + datetime.timedelta(days=13-today.weekday())
        start = today + datetime.timedelta(days=7-today.weekday())
        next_weeks_events = upcoming_events.filter(start_time__range=(start,end))
        pages = next_weeks_events.count() / EVENTS_PER_PAGE
        next_weeks_events = next_weeks_events.order_by('start_time')[int(num)*EVENTS_PER_PAGE:int(num)*EVENTS_PER_PAGE + EVENTS_PER_PAGE]
        event_sets.append( EventSet(u'Events Next Week', next_weeks_events) )
    elif date == u'flow':
        #flow code goes here
        pages = upcoming_events.count() / EVENTS_PER_PAGE
        flow_events = list( upcoming_events.order_by('start_time')[int(num)*EVENTS_PER_PAGE:int(num)*EVENTS_PER_PAGE + EVENTS_PER_PAGE] )
        #title = flow_events[0].start_time.strftime('%A, %B %-1d')
        #event_sets.append( EventSet(title, flow_events) )
        num_on_page = len(flow_events)
        if flow_events:
            flow_start = flow_events[0].start_time.replace(hour=0, minute=0, second=0)
        else:
            flow_start = today
        flow_end = flow_start.replace(hour=23,minute=59,second=59)
        keep_flowing = len(flow_events) > 0
        i = -1
        while keep_flowing == True:
            i = i + 1
            if i > 0: #advance to the next day
                flow_start = flow_start + datetime.timedelta(days=1)
                flow_end = flow_end + datetime.timedelta(days=1)
            current_days_events = [ x for x in flow_events if flow_start <= x.start_time < flow_end ]
            if len(current_days_events) == 0:
                continue
            # pull the title from the first event on the list
            title = current_days_events[0].start_time.strftime('%A, %B %-1d')
            # make the eventset
            event_sets.append( EventSet(title, current_days_events) )
            #update the tally
            num_on_page -= len(event_sets[-1].events)
            #check for pagination!
            if num_on_page <= 0:
                keep_flowing = False
        start = today
        end = None
    else:
        ISO8601_REGEX = re.compile(r'(?P<year>[0-9]{4})-(?P<month>[0-9]{1,2})-(?P<day>[0-9]{1,2})')
        exact_date = ISO8601_REGEX.match(date)
        if exact_date:
            group = exact_date.groupdict()
            start = datetime.datetime(year=int(group['year']), 
                             month=int(group['month']), 
                             day=int(group['day']) )
            end = start + datetime.timedelta(days=1)
            if old_tags != u'all':
                split_tags = old_tags.split(',')
                # Right now we query based on tags, and then later split this up based on date.
                # Does django make a query every time? If so this could be an expensive, inefficient way of
                # doing the job.
                upcoming_events = Event.events.filter(start_time__gte=start, tags__slug__in=split_tags).distinct()
            else:
                upcoming_events = Event.events.filter(start_time__gte=start)

            exact_day_events = upcoming_events.filter(start_time__range=(start,end))
            pages = exact_day_events.count() / EVENTS_PER_PAGE
            exact_day_events = exact_day_events.order_by('start_time')[int(num)*EVENTS_PER_PAGE:int(num)*EVENTS_PER_PAGE + EVENTS_PER_PAGE]
            event_sets.append( EventSet( u'Events for ' + start.date().strftime('%A, %B %-1d') , exact_day_events))
        else:
            #we need to 404 error here...
            raise Http404
            
    #packaging new tag information given split_tags list
    tags = Tag.objects.all()
    all_tags = []
    for tag in tags:
        if end is None:
            number_of_events = Event.events.filter(start_time__gte=start, tags__name__in=[tag]).count()
        else:
            number_of_events = Event.events.filter(start_time__range=(start,end), tags__name__in=[tag]).count()
        all_tags.append(
            TagInfo(
                tag=tag, #the tag object
                previous_slugs=split_tags, #list of existing tags
                num=number_of_events #number of events which are tagged this way
                )
            )
    all_tags.sort(key=lambda tag: tag.name)
    all_tags.sort(key=lambda tag: tag.number, reverse=True)
    if end is None:
    	    	all_tags.insert(0, TagInfo( num=Event.events.filter(start_time__gte=start).count(), previous_slugs=split_tags)) #this is the fake "all catagories" tag
    else:
    	all_tags.insert(0, TagInfo( num=Event.events.filter(start_time__range=(start,end)).count(), previous_slugs=split_tags)) #this is the fake "all catagories" tag

    # NUMCODE: This code is here because the page numbers start at 1 (which is never displayed or linked to)
    # and according to the resident HCI guru, people like counting from 1
    # but I use it in the date filter code as a multiplier, which I want to start at 0
    num = num + 1
    page_less = num - 1
    if num < 2:
        page_more = 2
    else:
        page_more = num +1

    return render_to_response('events/browse_events.html',
                              { 'upcoming_events':upcoming_events,
                                'all_tags':all_tags,
                                'current_tags':old_tags,
                                'page_date':date,
                                'page_num':int(num),
                                'event_sets':event_sets,
                                'pages':range(pages+1),
                                'page_less':page_less,
                                'page_more':page_more,
                                'browsing':True, 
                                'browse_bar':True,
                                },
                              context_instance = RequestContext(request))

def view(request, slug=None):
    try:
        event = Event.events.get(slug=slug)
    except ObjectDoesNotExist:
        return HttpResponseRedirect(reverse('event_browse'))
    
    return render_to_response('events/event_description.html',
                              { 'event': event,
                                'browsing':True,
                                },
                              context_instance = RequestContext(request))

def create(request, form_class=None, success_url=None,
           template_name='events/create_event.html', send_email=True):
    if form_class == None:
        exclude = ['owner', 'authentication_key', 'slug']
        if request.user.is_authenticated():
            exclude.append('email')
        form_class = generate_form(*exclude)

    if request.method == 'POST':
        form = form_class(data=request.POST, files=request.FILES)
        if form.is_valid():
            event_obj = form.save(commit=False)

            if request.user.is_authenticated():
                #if logged in, use the users info to complete form
                event_obj.owner = request.user
                event_obj.email = request.user.email #don't really need this line

            
            # make sure the picture field is filled before saving!
            if 'picture' in request.FILES:
                path = picture_file_path(instance=event_obj,
                                         filename=request.FILES['picture'].name)
                event_obj.picture = path
                new_file = event_obj.picture.storage.save(path,
                                                          request.FILES['picture'])
                
            event_obj = event_obj.save() #save to the database
            form.save_m2m() #needed for many-to-many fields

            #email the user
            current_site = settings.EVENT_EMAIL_SITE
            subject = render_to_string('events/creation_email_subject.txt',
                                       { 'site': current_site,
                                         'title': mark_safe(event_obj.name) })

            subject= ''.join( subject.splitlines() )  # Email subjects are all on one line

            message = render_to_string('events/creation_email.txt',
                                       { 'authentication_key': event_obj.authentication_key,
                                         'slug': event_obj.slug,
                                         'site': current_site } 
                                       )
            
            msg = EmailMessage( subject,
                       message, 
                       DEFAULT_FROM_EMAIL, 
                       [event_obj.email] )
            msg.content_subtype = 'html'
            msg.send()
            # on success, redirect to the home page by default
            # if the user is authenticated, take them to their event page
            if success_url is None:
                success_url = reverse('event_created',kwargs={ 'slug':event_obj.slug})
            #send user off into the abyss...
            return HttpResponseRedirect(success_url)
        
    else:
        form = form_class()
    #Send out the form
    context = RequestContext(request)
    return render_to_response(template_name,
                              { 'form': form,
                                'posting':True,
                                #'hide_end':form.end_time != ''
                                },
                              context_instance=context)

def created(request, slug=None):
    if slug is None:
        raise Http404
    return render_to_response('events/creation_complete.html',
                              { 'slug':slug,
                                'posting':True, 
                                },
                              context_instance=RequestContext(request))

def edit(request, 
         form_class=None, success_url=None, authentication_key=None,
         template_name='events/edit_event.html'):

    # Define the form to be used. This allows for anonymous creation of events.
    if form_class == None:
        form_class = generate_form('owner', 'authentication_key', 'slug', 'email')

    # Event object is retrieved based on incoming path hash
    # If the hash does not match an existing event, the user
    # is redirected to the event creation page.
    try:
        event_obj = Event.events.get(authentication_key__exact=authentication_key)
    except ObjectDoesNotExist:
        return HttpResponseRedirect(reverse('event_create'))

    # Set the return address
    if success_url is None:
        success_url = reverse('event_view', kwargs={ 'slug':event_obj.slug})

    # Verify and save the form to model
    if request.method == 'POST':
        form = form_class( instance = event_obj,
                              files = request.FILES,
                               data = request.POST )
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(success_url)
    else:
        form = form_class(instance = event_obj)

    # Edit the event
    context = RequestContext(request)
    return render_to_response(template_name,
                              { 'form': form,
                                'event':event_obj,
                                'picture_exists': event_obj.picture_exists(40)},
                              context_instance=context)

