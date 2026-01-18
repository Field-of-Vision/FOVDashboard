### 21/4/25 

Was having lots of issues with the dashboard not working during deployment, and it being hard to debug. 
*Simply deleting the `.db` database* file that had existed seemed to fix all those issues. We now have logs
per device, and also can clearly see which is connected or not. 

Update: the above only seems to work for a few minutes, and then stops working. 

### 2/6/26 

Our marvel.fovdashboard and our aviva.fovdashboard will be listening and publishing to different topics!
We need a clear way to separate these... will just hardcode for now!\