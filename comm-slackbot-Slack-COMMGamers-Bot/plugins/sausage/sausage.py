from random import randrange
import requests 

bot_user = 'U041TJU13'
#kenny       = 'U040NP71B' #really paul
irc_channel = 'C040NNZHT'
response_interval = 20

def process_message(data):
    message_text = data.get('text')
    if message_text: 
        if (bot_user in message_text) and ('sausage' in message_text):
            response = requests.get('http://meanduino.paulnurkkala.com/sausage/')
            response = requests.get('http://meanduino.paulnurkkala.com/sausages/count')

            resp_data = response.json()
            count = resp_data['count']

            available_sausages = [
                'http://i.imgur.com/nLSNBEz.jpg', 
                'http://i.imgur.com/1TDxr2L.jpg', 
                'http://i.imgur.com/PSJpIeh.jpg',
                'http://i.imgur.com/EMpWbBW.jpg',
                'http://i.imgur.com/GPN780S.jpg',
                'http://i.imgur.com/dz0uTjO.jpg',
                'http://i.imgur.com/oDKsBsu.jpg'
            ]

            #pick the available_sausages
            rand_num = randrange(0, len(available_sausages))
            active_sausage = available_sausages[rand_num]

            outputs.append([irc_channel, '`SAUSAGE!`'])
            outputs.append([irc_channel, active_sausage])
            outputs.append([irc_channel, '`We are now at: %s sausages.`' % count])
