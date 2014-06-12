Imazon-Sad application
======================

This is a highly specialized application to track deforestation on the Amazonas. More specifically,
it is a tool to do validation of deforestation detected by algorithms using satellite imagery.
The algorithm and the methodology has been developed by Imazon (TODO: links to scientific papers).
The frontend and the application architecture has been developed by Vizzuality and updated by Google. 
The backend support for Google Earth Engine has been provided by David Thau. 

The tool runs on Google App Engine (GAE) and uses Google Earth Engine (GEE) and Fusion Tables (FT) APIs.
You may need certain API keys to run the application - contact thau@google.com for details.

How to run the application
--------------------------

The tool is intended to be use directly online (still pending the final URL) so the following instructions
only apply for developers on the project. The instructions are specific for development under Mac OS X Lion
and Snow Leopard, but it shouldn't be complicated to make it run in other Unix-like systems.

1. Install the [App Engine Python SDK](http://code.google.com/intl/en/appengine/downloads.html#Google_App_Engine_SDK_for_Python)
   * Run it and let it make symbolic links (you will be asked to enter your root password)
2. Modify appengine to use Python 2.7.
   * Go to terminal and write: `mate /Applications/GoogleAppEngineLauncher.app/Contents/Resources/GoogleAppEngine-default.bundle/Contents/Resources/google_appengine/dev_appserver.py`
   * Modify the first line to say: `#!/usr/bin/python2.7`
3. Checkout the project from GitHub.
   * In the terminal go to the folder where you want to install the code: `cd /Users/me/workspace/`
   * Run `git clone git://github.com/Vizzuality/DeforestationAnalysisTool.git`
4. Copy and modify `secret_keys.py.example`.
   * run `cp src/application/secret_keys.py.example src/application/secret_keys.py`
   * Edit it accordingly (ask thau@google.com for credentials).
5. Run the application.
   * Go to the src folder: `cd src`
   * Run it using the following script: `./tools/start`. Leave the window open.
6. Create an initial report.
   * Open a new Terminal window, leaving the other open,
   * Initialize fusion tables: `curl "http://localhost:8080/_ah/cmd/fusion_tables_names"`
   * Create an unclosed report: `curl -d '' "http://localhost:8080/_ah/cmd/create_report?year=2011&month=7&day=15"`
   * Optionally, create a closed report: `curl -d '' "http://localhost:8080/_ah/cmd/create_report?year=2011&month=8&day=15&fyear=2011&fmonth=9&fday=15&assetid=SAD_VALIDATED/SAD_2010_05"`
7. Start using the app.
   * You should now be able to go to `http://localhost:8080` and start using the application locally.
   * When logging in, don't forget to set yourself as admin.

Screenshots
-----------
![Alt text](http://vizzuality.s3.amazonaws.com/blogImages/imazon/1.png)
![Alt text](http://vizzuality.s3.amazonaws.com/blogImages/imazon/2.png)
![Alt text](http://vizzuality.s3.amazonaws.com/blogImages/imazon/3.png)
![Alt text](http://vizzuality.s3.amazonaws.com/blogImages/imazon/4.png)
![Alt text](http://vizzuality.s3.amazonaws.com/blogImages/imazon/5.png)
![Alt text](http://vizzuality.s3.amazonaws.com/blogImages/imazon/6.png)
![Alt text](http://vizzuality.s3.amazonaws.com/blogImages/imazon/8.png)
![Alt text](http://vizzuality.s3.amazonaws.com/blogImages/imazon/9.png)
