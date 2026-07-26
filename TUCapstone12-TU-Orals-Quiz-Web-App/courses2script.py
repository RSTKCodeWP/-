filename = "Courses"
with open("%s.csv"%filename,"r") as ifile:
	lines = ifile.readlines()

chead = "DELETE FROM Course;\nINSERT INTO Course (cid, name) VALUES\n"
courses = []	
for course in lines:
	data = course.split(",")
	cid = data[0]
	cid = cid[:3]+cid[4:] #Remove space
	cname = data[1][:-1] #Remove \n
	courses.append("""("%s", "%s")"""%(cid, cname))

with open("%s.sql"%filename,"w") as ofile:
	ofile.write(chead+", \n".join(courses)+";")