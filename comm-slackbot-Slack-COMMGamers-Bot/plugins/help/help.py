from random import randrange
import requests 

bot_user = 'U041TJU13'
#kenny       = 'U040NP71B' #really paul
irc_channel = 'C040NNZHT'
response_interval = 20

def process_message(data):
    message_text = data.get('text')
    if message_text: 
        if (bot_user in message_text) and ( ('help' in message_text) or ('commands' in message_text)):
        	available_commands = [
        	    '`source  -- view my code`',
        	    '`sausage -- print a sausage`',
        	    '`test    -- make sure I\'m alive`',
        	    '`help    -- list these commands`' 
        	]

        	outputs.append([irc_channel, '`To send a command, @tag me and type any of the following to perform the action.`'])

        	for com in available_commands: 
        	    outputs.append([irc_channel, com])