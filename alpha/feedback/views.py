# Create your views here.
from .forms import ContactForm
from .models import Feedback
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.core.mail import send_mail
from django.core.urlresolvers import reverse

def feedback(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            message = 'From: %(name)s <%(email)s>\n\n%(type)s\n\n%(comments)s' % form.cleaned_data
            send_mail("cityfusion.ca Feedback", message, 'feedback@cityfusion.ca',
                      ['levi@peakxp.com', 'tony@peakxp.com', 'sam@peakxp.com'], fail_silently=True)
            feedback = Feedback(**form.cleaned_data)
            feedback.save()
            return HttpResponseRedirect( reverse('feedback_thanks') )
    else:
        form = ContactForm()

    return render_to_response("feedback/contact.html",
                              { 'form' : form },
                              context_instance=RequestContext(request))

def feedback_thanks(request):
    return render_to_response("feedback/contact_thanks.html",
                              {}, context_instance=RequestContext(request))
