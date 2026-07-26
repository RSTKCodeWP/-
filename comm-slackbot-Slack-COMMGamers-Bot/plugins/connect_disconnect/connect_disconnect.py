outputs = []
kenny       = 'U040QC43H'
#kenny       = 'U040NP71B' #really paul
irc_channel = 'C040NNZHT'

def catch_all(data):
    presence    = data.get('presence')
    change_type = data.get('type')

    if change_type == 'presence_change':
        if presence == 'away':
            outputs.append([irc_channel, '`A user has gone away.`'])
        if presence == 'active': 
            outputs.append([irc_channel, '`A new challenger approaches.`'])           
