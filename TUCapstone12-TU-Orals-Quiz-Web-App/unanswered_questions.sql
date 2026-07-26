SELECT Q.qid, question
FROM Question Q LEFT OUTER JOIN Answer A ON Q.qid = A.qid
WHERE A.qid is NULL
