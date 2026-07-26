irc_channel = 'C040NNZHT'
bot_user = 'U041TJU13'
outputs = []

def process_message(data):
    message_text = data.get('text')
    if message_text:
        if(bot_user in message_text) and ('test' in message_text):
            outputs.append([irc_channel, '`huh?`'])