### utils.py ### 
from django.conf import settings

def build_pb_url():
	#example https://www.pushbullet.com/authorize?client_id=YW7uItOzxPFx8vJ4&redirect_uri=http%3A%2F%2Fwww.catpusher.com%2Fauth_complete&response_type=code

	#build access token granter URL 
	pb_url           = None
	pb_url_base      = 'https://www.pushbullet.com/authorize'
	pb_client_id     = 'client_id=%s' % settings.PUSHBULLET_ID
	pb_redirect_uri  = 'redirect_uri=%s' % settings.PUSHBULLET_REDIRECT_URI
	pb_response_type = 'response_type=%s' % 'code'

	pb_url = '%s?%s&%s&%s' % (pb_url_base, pb_client_id, pb_redirect_uri, pb_response_type)

	return pb_url


### views.py ###
from django.shortcuts import render
from django.http import HttpResponse
from django.conf import settings

from .utils import build_pb_url

import requests 

def pb_start(request):
	"""example page to start pushbullet authentication """
	pb_url = build_pb_url
	return render(
		request, 
		'start_pb.html', 
		{
		    'pb_url': pb_url, 
		}, 
	)

def pb_redirect_url(request): 
	"""pushbullet returns to this url """

	code = request.GET.get('code')

	if not code: 
		print 'something terrible has happened'
	else: 
		pb_token_url = 'https://api.pushbullet.com/oauth2/token'
		payload = {}
		payload['grant_type']    = 'authorization_code'
		payload['client_id']     = settings.PUSHBULLET_ID
		payload['client_secret'] = settings.PUSHBULLET_SECRET
		payload['code']          = code
		#authorization_token      = 'Basic %s:' % code

		response = requests.post(pb_token_url, data=payload)

		if response.ok: 
			response_data = response.json()
			access_token = response_data.get('access_token')
			request.user.pushbullet_token = access_token
			request.user.save()
  		    
  		    #send a push to the user 
			request.user.push_pb_note('Congratulations!', 'We can now send CaterZing notifications directly to your devices!')
		else:
			return HttpResponse("An error occurred while fetching your token.")

	return render(
		request, 
		'authorized_pb.html', 
		{},
	)



### start_pb.html ###
{% extends 'base.html' %}

{% block head %}
{% endblock %}

{% block breadcrumbs %}
	<li><a href="#">Pushbullet Authentication</a></li>
{% endblock %}

{% block content %}
	<legend><h3>Link PushBullet</h3></legend>

	<div class="row">
		<div class="col-md-8">
			<legend>Why Link your PushBullet account? </legend>
			<h4>What is PushBullet?</h4>
			<blockquote>
				<p>
					"Pushbullet connects your devices, making it easy and automatic to share almost anything between them." -- <a href="https://pushbullet.com">PushBullet.com</a>  
				</p>
			</blockquote>
			<p>
				By <a href="{{pb_url}}">linking</a> to PushBullet, you'll be able to get notifcations from ______ instantly on all your devices. Your computer, tablet, and phone call at get a notification whenever anything happens on the site. 
			</p>
			<p>
				With PushBullet, you can always stay up to date, and get the information you need instantly wherever you might need it. 
			</p>
			<img src="{{STATIC_URL}}images/pushbullet.png" alt="pushbullet details" class="img-responsive img-thumbnail">
		</div>
		<div class="col-md-4">
			<legend>Link Now</legend>
			<a class="btn btn-default btn-lg" href="{{pb_url}}">Link Pushbullet <img style="height:60px" src="{{STATIC_URL}}images/pushbullet_logo.jpg" class="img-responsive img-thumbnail"></a>
		</div>
		
	</div>

{% endblock %}



### authorized_pb.html ###
{% extends 'base.html' %}

{% block head %}
{% endblock %}

{% block breadcrumbs %}
	<li><a href="#">Pushbullet Authentication</a></li>
{% endblock %}

{% block content %}
	<legend><h1>Congratulations!</h1></legend>
	<div class="row">
		<div class="col-md-6">
			<p>
				You have given CaterZing permission to send pushbullet notifications directly to your devices. This means that you can always stay up to date with the goings on of your restaurant!
			</p>				
		</div>
		<div class="col-md-6">
			<img src="{{STATIC_URL}}images/pushbullet.png" alt="pushbullet details" class="img-responsive img-thumbnail">
		</div>
	</div>


{% endblock %}


### urls.py ###
from django.conf.urls import patterns, include, url
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin

import pb_auth.views as pb_auth_views

urlpatterns = patterns('',
	url(r'^start/$', pb_auth_views.pb_start, name="pb-start"), 
	url(r'^authenticate/$', pb_auth_views.pb_redirect_url, name="pb-authenticate"), 

)


### user models.py ###

class User(AbstractBaseUser, PermissionsMixin):
    """User model to override the base user. This has extra fields that are specific to the TrueU project. Inherits from the base Auth user stuff."""

    pushbullet_token = models.CharField(max_length=500, null=True, blank=True)
