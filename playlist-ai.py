import streamlit as st
import os
from openai import OpenAI
import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth

def get_token(oauth, code):
    token = oauth.get_access_token(code, as_dict=False, check_cache=False)
    # remove cached token saved in directory
    os.remove(".cache")
    
    # return the token
    return token


def sign_in(token, oauth):
    sp = spotipy.Spotify(auth=token, auth_manager=oauth)
    return sp


# def get_correct_limit(stop, start):
    
#     # start at 50 and move backwards until correct timestamp is found
#     # re run the API call until 'before' is greater than the stop timestamp
#     limit = 50
#     while limit > 0:
#         obj = sp.current_user_recently_played(before=start, limit=limit)
#         mark = int(obj['cursors']['before'])
        
#         # get the track played right after the stop timestamp
#         if mark > stop:
#             break
#         # otherwise, decrease the limit by 1 and try again
#         limit -= 1
    
#     return limit


def app_get_token():
    try:
        token = get_token(st.session_state["oauth"], st.session_state["code"])
    except Exception as e:
        st.error("An error occurred during token retrieval!")
        st.write("The error is as follows:")
        st.write(e)
    else:
        st.session_state["cached_token"] = token



def app_sign_in():
    try:
        sp = sign_in(st.session_state["cached_token"], st.session_state["oauth"])
    except Exception as e:
        st.error("An error occurred during sign-in!")
        st.write("The error is as follows:")
        st.write(e)
    else:
        st.session_state["signed_in"] = True
        app_display_welcome()
        # st.success("Sign in success!")
    return sp


def app_display_welcome():
    
    # import secrets from streamlit deployment
    cid = st.secrets["SPOTIPY_CLIENT_ID"]
    csecret = st.secrets["SPOTIPY_CLIENT_SECRET"]
    uri = st.secrets["SPOTIPY_REDIRECT_URI"]

    # set scope and establish connection
    scopes = " ".join(["user-read-private",
                       "user-read-email",
                       "playlist-read-private",
                       "playlist-modify-private",
                       "playlist-modify-public",
                       "user-read-recently-played"])

    oauth = SpotifyOAuth(scope=scopes,
                         redirect_uri=uri,
                         client_id=cid,
                         client_secret=csecret)
    st.session_state["oauth"] = oauth

    auth_url = oauth.get_authorize_url()
    
    # this SHOULD open the link in the same tab when Streamlit Cloud is updated via the "_self" target
    link_html = " <a target=\"_self\" href=\"{url}\" >{msg}</a> ".format(
        url=auth_url,
        msg="Log in"
    )
    
    welcome_msg = """
    Welcome! :wave: This app allows you to generate Spotify playlists
    based on whatever prompt you input. Log in below to get started!
    """

    st.title("PlaylistAI")

    if not st.session_state["signed_in"]:
        st.markdown(welcome_msg)
        st.write(" ".join(["Please log in by",
                          "clicking the link below."]))
        st.link_button("Log in", auth_url)
        # st.markdown(link_html, unsafe_allow_html=True)        
        
        
def generate_playlist(output, user):
    track_ids = []
    key = ""
    if "songs" in output:
        key = "songs"
    elif "tracks" in output:
        key = "tracks"
    else:
        st.write("error parsing json")
        return 
    for x in output[key]:
        if "song" in x:
            track = x["song"]
        elif "name" in x:
            track = x["name"]
        elif "title" in x:
            track = x["title"]
        elif "song_title" in x:
            track = x["song_title"]
        elif "track_name" in x:
            track = x["track_name"]
        artist = x["artist"]
        search = sp.search(q='artist:' + artist + ' track:' + track, limit=1, type='track')['tracks']['items']
        if len(search) > 0:
            track_ids.append(search[0]['id'])
    
    playlist = sp.user_playlist_create(user["id"], output["playlist_name"], public=True, collaborative=False, description=output["description"])
    sp.playlist_add_items(playlist["id"], track_ids)
    for x in track_ids:
        st.image(track(x)["album"]["images"]["url"], width=300)
    return playlist

   
# %% app session variable initialization

if "signed_in" not in st.session_state:
    st.session_state["signed_in"] = False
if "cached_token" not in st.session_state:
    st.session_state["cached_token"] = ""
if "code" not in st.session_state:
    st.session_state["code"] = ""
if "oauth" not in st.session_state:
    st.session_state["oauth"] = None

# %% authenticate with response stored in url

# get current url (stored as dict)
url_params = st.query_params
sp = ""
# attempt sign in with cached token
if st.session_state["cached_token"] != "":
    sp = app_sign_in()
# if no token, but code in url, get code, parse token, and sign in
elif "code" in url_params:
    # all params stored as lists, see doc for explanation
    st.session_state["code"] = url_params["code"][0]
    # app_get_token()
    cid = st.secrets["SPOTIPY_CLIENT_ID"]
    csecret = st.secrets["SPOTIPY_CLIENT_SECRET"]
    uri = st.secrets["SPOTIPY_REDIRECT_URI"]

    # set scope and establish connection
    scopes = " ".join(["user-read-private",
                       "user-read-email",
                       "playlist-read-private",
                       "playlist-modify-private",
                       "playlist-modify-public",
                       "user-read-recently-played"])

    oauth = SpotifyOAuth(scope=scopes,
                         redirect_uri=uri,
                         client_id=cid,
                         client_secret=csecret)
    st.session_state["oauth"] = oauth
    sp = app_sign_in()

# otherwise, prompt for redirect
else:
    app_display_welcome()
    
# %% after auth, get user info

# only display the following after login
if st.session_state["signed_in"]:
    user = sp.current_user()
    name = user["display_name"]
    username = user["id"]

    st.markdown("Hi {n}! Let's create a playlist or two :smiley:".format(n=name))
    
    client = OpenAI()
    OpenAI.api_key = os.getenv('OPENAI_API_KEY')


    st.write('Welcome to PlaylistAI!')
    input = st.text_input('Describe the playlist you want')
    submit = st.button('Submit')

    if input or submit:
        completion = client.chat.completions.create(
            model="gpt-3.5-turbo",
            response_format={ "type": "json_object" },
            messages=[
                {"role": "system", "content": "You are a an expert in making Spotify playlists."},
                {"role": "user", "content": "Create a 30 song Spotify playlist according to the following prompt:" + input + "and output in json format"}
            ]
        )
        outputDict = json.loads(completion.choices[0].message.content)
        st.write(outputDict)
        playlist = generate_playlist(outputDict, user)
        st.write(playlist["id"])
        for x in sp.playlist_items(playlist["id"])["items"]:
            st.write(x)
        st.write("Success!")
    
