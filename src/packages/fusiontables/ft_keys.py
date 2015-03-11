#!/usr/bin/python

#from fusiontables.ftclient import ClientLoginFTClient
#from fusiontables.ftclient import OAuthFTClient
#from fusiontables.authorization.oauth import OAuth
#from fusiontables.authorization.clientlogin import ClientLogin
#from fusiontables.sql.sqlbuilder import SQL


from ftclient import ClientLoginFTClient
from ftclient import OAuthFTClient
from authorization.oauth import OAuth
from authorization.clientlogin import ClientLogin
from sql.sqlbuilder import SQL


def clientlogin_example(username, password):
  clientlogin = ClientLogin()
  token = clientlogin.authorize(username, password)
  client = ClientLoginFTClient(token)
  print client.query(SQL().showTables())


def oauth_example(key, secret):
  oauthlogin = OAuth()
  url, oauth_token, oauth_token_secret = oauthlogin.generateAuthorizationURL(key, secret, key, None)
  print oauth_token
  print oauth_token_secret

  print url

  raw_input("hit enter")

  returned_token, oauth_secret = oauthlogin.authorize(key, secret, oauth_token, oauth_token_secret)

  client = OAuthFTClient(key, secret, returned_token, oauth_secret)
  print client.query("SELECT * FROM 316962")

if __name__ == "__main__":
  FT_CONSUMER_KEY = 'javisantana.com'
  FT_CONSUMER_SECRET = '9vJ0i9kf5WNey20D41CIF0YB'
  oauth_example(FT_CONSUMER_KEY, FT_CONSUMER_SECRET)

