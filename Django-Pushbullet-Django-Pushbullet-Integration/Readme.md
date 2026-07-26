# PushBullet Authentication 

This is a walkthrough of my pushbullet authentication process for my websites. Essentially, this code allows users of my sites to be able to authenticate their pushbullet accounts to allow me to push notifications to them. In this way, my websites have a push-notification system at which I can reach my users with any features that PushBullet offers.

The code presented is written in python for the Django framework, but the principles should apply to any framework or programming language that you decide to implement. 

## Model
The first thing you should do is update your models. For each user, they should have a field that saves their Pushbullet API token

    class User(AbstractBaseUser, PermissionsMixin):
        pushbullet_token = models.CharField(max_length=500, null=True, blank=True)

## Authentication URL Builder
This is simply a utility function that I wrote that will create a URL that starts the PushBullet Authentication: 

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
The next thing that I create are the URLS. There are two pages: 1 is used to begin the authentication process. This page explains the purpose of using pushbullet, and then, using the utility function, provides a link to begin the authentication process on the PushBullet server. The second, which receives a 'code' from PushBullet, fetches the user's token from pushbullet and saves it to their account, sending them a push, notifying them that they've been signed up for pushbullet.

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
	    
## You can also view the templates in the attached file. 

Now, any time that you want to send a push to a user, just use the python API that is in the library. 

[PushBullet Python API Link](https://github.com/randomchars/pushbullet.py)


