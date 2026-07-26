bot_user = 'U041TJU13'
irc_channel = 'C040NNZHT'

outputs = []

def process_message(data):
	message_text = data.get('text')
	if message_text: 
	    if (bot_user in message_text) and ('source' in message_text):
		    outputs.append([irc_channel, '`https://github.com/paulnurkkala/comm-slackbot`'])
