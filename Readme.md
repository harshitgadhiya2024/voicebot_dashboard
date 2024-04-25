School-project
A backend service in python to have talk with our system for users.

Deployment
Step: 1 clone github repo and check code

Step: 2 check dockerfile is present or not in your project

Step: 3 Exucute below commond for generate image docker build -t hgadhiya8980/crest-api:0.q.RELEASE . docker build -t {username/imagename:tag}

Step: 4 Create container docker container run -d -p 80:80 hgadhiya8980/crest-api:0.q.RELEASE docket container run -d -p {flaskport}:{forwardport} {yourimagename:yourtagname}

Step: 5 Check container log server is running?

Step: 6 Test your API