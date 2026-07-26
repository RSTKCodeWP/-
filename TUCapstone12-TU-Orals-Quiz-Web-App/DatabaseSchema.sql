CREATE TABLE Course (
        cid varchar(20) PRIMARY KEY NOT NULL,
	name varchar(20)
	);
CREATE TABLE Question (
	question varchar(20),
	qid  integer PRIMARY KEY NOT NULL,
	average_result real
	);
	
CREATE TABLE Answer (
	qid varchar(20),
	cid varchar(20),
	html varchar(20),
	answer varchar(20),
	PRIMARY KEY (qid,cid),
	FOREIGN KEY (qid) REFERENCES Question(qid),
	FOREIGN KEY (cid) REFERENCES Course(cid)
	);
	
	