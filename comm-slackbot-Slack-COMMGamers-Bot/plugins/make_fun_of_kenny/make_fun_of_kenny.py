from random import randrange

kenny       = 'U040QC43H'
#kenny       = 'U040NP71B' #really paul
irc_channel = 'C040NNZHT'
response_interval = 20

def process_message(data):
    user = data.get('user')
    if user == kenny:
        print 'Kenny has spoken!'
        say_insult()


def say_insult(): 
    insults = [
        'Shut up', 
        'Holy crap -- just drop it!',
        'Learn to listen', 
        'Geeeeeeeze, man!', 
        'Is there any point to your incessant noise??',
        'Just get back to work.. ', 
        'Hey! Intern! Quiet!', 
        'Put a lid on it!', 
        'Calm yourself.', 
        'http://i.imgur.com/YTllhWG.gif', 
        'http://i.imgur.com/cGYTBP9.gif', 
        'http://i.imgur.com/HXBldo9.gif', 
        'http://i.imgur.com/d5R53eM.gif', 
        'http://i.imgur.com/4AtcAKs.gif',
        'http://i.imgur.com/RXQPENV.gif', 
    ]

    #pick the insult
    rand_num = randrange(0, len(insults))
    active_insult = insults[rand_num]

    #determine whether or not this is a time to insult 
    random = randrange(0, response_interval)
    do_say = random % response_interval

    #if the modulus is zero
    if not do_say: 
        active_insult = "`@lastnamefirst %s `" % active_insult

        outputs.append([irc_channel, active_insult])
