from re import match, escape, sub

def fix_str(in_str):
	out_str = sub('"',"\\\"",in_str)
	return out_str
	
filename = "Questions2"
in_file  = open("%s.csv" %filename,"r")
lines = in_file.readlines()
in_file.close()
qhead = "DELETE FROM Question;\nINSERT INTO Question (qid, question, average_result) VALUES \n"
questions = []
ahead = "DELETE FROM Answer;\nINSERT INTO Answer (qid, cid, answer, username) VALUES \n"
answers = []
count = 0
lineIndex = 0
for line in lines[1:]:
	lineIndex += 1
	if line == ",,,,,,":
		continue
	data = line.split(",")
	print("%s - %s" % (count, len(data)))
	count = count + 1
	qid = data[0]
	if len(qid) == 0:
		continue
	name = data[1]
	if len(name) == 0:
		name = "NULL"
	else:
		name = "\"%s\""%name
	progress = data[2]
	avg = data[3]
	question = fix_str(data[4])
	cname = data[5]
	if not match("[A-Z]{3}\d{3}$",cname):
		cname = "NULL"
	else:
		cname = "\"%s\""%cname #Surround in ""'s
	answer = fix_str(data[6])[:-1] #Should remove /n
	for nextLine in lines[lineIndex+1:]:
		nextData = nextLine.split(",")
		nextQid = nextData[0]
		if nextQid != "":
			break
		nextQuestion = fix_str(nextData[4])
		if nextQuestion == "":
			continue
		question += "\n"+nextQuestion;
	questions.append("""("%s", "%s", %s)""" % (qid, question, avg))
	if len(answer) > 0:
		answers.append("""("%s", %s, "%s", %s)""" % (qid, cname, answer, name))

outfile = open("%s.sql"%filename,"w")
outfile.write(qhead+", \n".join(questions)+";\n\n"+ahead+", \n".join(answers)+";")
outfile.close()

		
