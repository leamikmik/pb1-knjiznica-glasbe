import bottle
import json
import os
import datetime
from model import User, Song, Release, Playlist

SECRET = "giheihs"

def del_cookie(cookie):
    """izbriše dan cookie"""
    bottle.response.delete_cookie(cookie, path="/")

def set_cookie(cookie, message):
    """ustvati cookie s podanim imenom ter vsebino"""
    bottle.response.set_cookie(cookie, message, secret=SECRET, path="/")

def get_cookie(cookie, delete=True):
    """vrne vsebino podanega cookieja, po privzetem ga izbriše"""
    message=bottle.request.get_cookie(cookie, secret=SECRET)
    if delete:
        del_cookie(cookie)
    return message

def set_message(message):
    """ustvari cookie z imenom 'msg' in podano vsebino"""
    set_cookie("msg", message)

def read_message():
    """vrne vsebino cookieja z imenom 'msg', ga izbriše"""
    message=get_cookie('msg')
    del_cookie('msg')
    return message

def set_form(cookie, form):
    """ustvari obrazec s podanim imenom ter privzetimi vredenostmi iz podanega slovarja"""
    set_cookie(cookie, json.dumps(form))

def read_form(cookie, default={}, delete=True):
    """vrne vrednosti cookieja s podanim imenom in ga po privzetem izbriše, če je ta cookie obrazec, 
    sicer po privzetem vrne prazen slovar"""
    try:
        return json.loads(get_cookie(cookie, delete))
    except (TypeError, json.JSONDecodeError):
        return default

def logged_in_user():
    """vrne prijavljenega uporabnika, če ga ni vrne False"""
    uid=bottle.request.get_cookie('user', secret=SECRET)
    try:
        user = User(uid)
    except ValueError:
        return False
    return user

def login_user(user, cookie="None"):
    """ustvari cookie za podanega uporabnika in preusmeri na domačo stran."""
    if not user:
        set_message("user not found")
        bottle.redirect("/prijava/")
    bottle.response.set_cookie('user', user.id, secret=SECRET, path="/")
    if cookie:
        del_cookie(cookie)
    bottle.redirect("/")

def logout_user():
    """odjavi prijavljenega uporabnika"""
    del_cookie('user')
    bottle.redirect('/')

def epoch_to_str(epoch):
    """epoch čas spremeni v niz"""
    date = datetime.datetime.fromtimestamp(epoch)
    yr, mn, d = str(date)[:-9].split("-")
    return f"{d}/{mn}/{yr}"


# Statične datoteke
@bottle.get('/static/<file:path>')
def static(file):
    return bottle.static_file(file, root='static')

@bottle.get('/music/<file:path>')
def static_music(file):
    return bottle.static_file(file, root='music')

@bottle.get('/temp/<file:path>')
def static_temp(file):
    return bottle.static_file(file, root='temp')


# Domača stran
@bottle.get('/')
@bottle.view('index.html')
def index():
    pass

# Prijava
@bottle.get('/prijava/')
@bottle.view('login.html')
def login():
    pass

@bottle.post('/prijava/')
def login_post():
    username=bottle.request.forms.username
    password=bottle.request.forms.password
    set_form('login', {'username':username})
    try:
        user = User.login(username, password)
    except:
        set_message("Napačno uporabniško ime ali geslo.")
        bottle.redirect("/prijava/")
    login_user(user, cookie='login')

# Registracija
@bottle.get('/registracija/')
@bottle.view('registration.html')
def register():
    pass

@bottle.post('/registracija/')
def register_post():
    username=bottle.request.forms.username
    password1=bottle.request.forms.password1
    password2=bottle.request.forms.password2
    if username=="" or password1=="":
        set_message("Prosim, vnesite uporabniško ime in geslo.")
        bottle.redirect("/registracija/")
    set_form('register', {'username': username})
    if password1 != password2:
        set_message('Gesli se ne ujemata.')
        bottle.redirect('/registracija/')
    user=User.register(username, password1)
    login_user(user, cookie='login')

@bottle.get('/odjava/')
def odjava():
    logout_user()

# Brskalnik pesmi
@bottle.get('/pesmi/')
@bottle.view('songsearch.html')
def song_search():
    query = bottle.request.query.query
    if query:
        results = Song.search(query)
    else:
        results = Song.search("")
    return dict(query=query, results=results)

# Brskalnik uporabnikov
@bottle.get('/izvajalci/')
@bottle.view('usersearch.html')
def user_search():
    query = bottle.request.query.query
    if query:
        results = User.search(query)
    else:
        results = User.search("")
    return dict(query=query, results=results)

# Brskalnik izdaj
@bottle.get('/izdaje/')
@bottle.view('releasesearch.html')
def release_search():
    query = bottle.request.query.query
    if query:
        results = Release.search(query, "album")
        results.extend(Release.search(query, "single"))
        results.extend(Release.search(query, "ep"))
    else:
        results = Release.search("", "album")
        results.extend(Release.search("", "single"))
        results.extend(Release.search("", "ep"))
    return dict(query=query, results=results)

# Posamezna izdaja
@bottle.get('/izdaje/<id:int>/')
@bottle.view('release.html')
def release_songs(id):
    release = Release(id)
    songs = release.songs
    return dict(release=release, songs=songs)

# Posamezen uporabnik
@bottle.get('/uporabniki/<id:int>/')
@bottle.view('user.html')
def user_info(id):
    user = User(id)
    releases = user.releases
    date = epoch_to_str(user.date) 
    return dict(releases=releases, _user=user, date=date)

# Ustvarjanje nove izdaje
@bottle.get('/nalaganje/')
@bottle.view('makerelease.html')
def make_release_get():
    _user = logged_in_user()
    if not _user:
        bottle.redirect('/prijava/')
    return dict(releases=_user.releases)

@bottle.post('/nalaganje/')
def make_release_post():
    _user=logged_in_user()
    type=bottle.request.forms.type
    title=bottle.request.forms.title
    r_id=Release.new_release(_user.id, title, type, "./music/")
    bottle.redirect(f'/nalaganje/{r_id}/')

# Nalaganje nove pesmi v izdajo
@bottle.get('/nalaganje/<r_id:int>/')
@bottle.view('upload.html')
def upload_get(r_id):
    return dict(r_id=r_id)

@bottle.post('/nalaganje/<r_id:int>/')
def upload_post(r_id):
    _user=logged_in_user()
    release=Release(r_id)
    if release.author.id != _user.id:
        set_message("Samo avtor izdaje lahko ji dodaja pesmi.")
        bottle.redirect('/')   
    title=bottle.request.forms.title
    file = bottle.request.files.get('upload', '')
    filename = file.filename
    _, ext = os.path.splitext(filename)
    if ext != ".mp3":
        set_message("Dovoljeno je nalaganje samo mp3 datotek.")
        bottle.redirect(f'/nalaganje/{r_id}/')
    destination=os.path.join(".", "music", str(r_id))
    order_num=len(release.songs)
    if not os.path.isdir(os.path.join(".", "temp")):
        os.mkdir(os.path.join(".", "temp"))
    path=os.path.join(".", "temp")
    if not os.path.isfile(os.path.join(path, filename)):
        file.save(path)
    Song.new_song(r_id, order_num, title, os.path.join(path, filename), destination)
    set_message("Pesem uspešno naložena.")
    bottle.redirect(f'/nalaganje/{r_id}/')

# Seznami prijavljenega uporabnika
@bottle.get('/seznami/')
@bottle.view('userplaylists.html')
def playlists_get():
    _user=logged_in_user()
    if not _user:
        bottle.redirect('/prijava/')
        set_message("Za sezname predvajanj morate biti prijavljeni.")
    playlists=_user.playlists
    return dict(playlists=playlists)

# Ustvarjanje novega seznama
@bottle.post('/seznami/')
def make_playlist_post():
    _user=logged_in_user()
    name=bottle.request.forms.name
    p_id=Playlist.create(_user.id, name)
    bottle.redirect(f'/seznami/dodaj/{p_id}/')

# Posamezen seznam
@bottle.get('/seznami/<pid:int>/')
@bottle.view('playlist.html')
def playlist_view(pid):
    playlist=Playlist(pid)
    return dict(playlist=playlist, songs=playlist.songs)

# Dodajanje pesmi v seznam
@bottle.get('/seznami/dodaj/<pid:int>/')
@bottle.view('playlistadd.html')
def add_to_playlist(pid):
    _user=logged_in_user()
    playlist=Playlist(pid)
    pl_song_ids=playlist.songs_id
    if not _user:
        bottle.redirect('/prijava/')
        set_message("Za sezname predvajanj morate biti prijavljeni.")
    if _user.id != playlist.owner.id:
        set_message("Urejate lahko samo svoje sezname predvajanj.")
        bottle.redirect('/')
    query = bottle.request.query.query
    if query:
        results = Song.search(query)
    else:
        results = None
    if bottle.request.query.get(f"start", ""):
        i = 0
        failed = []
        while bottle.request.query.get(f"{i}song", "") != "stop":
            song_to_add = bottle.request.query.get(f"{i}song", "")
            if song_to_add:
                if int(song_to_add) not in pl_song_ids:
                    playlist.add_song(song_to_add)
                else:
                    failed.append(song_to_add)
            i += 1
        print(failed)
        if failed:
            set_message(f"Naslednje pesmi so že v seznamu: {str([Song(sid).title for sid in failed])[1:-1]}.")
            bottle.redirect(f"/seznami/dodaj/{pid}/")
    return dict(query=query, results=results, playlist=playlist)
  


# Predložene funkcije
bottle.BaseTemplate.defaults["read_message"] = read_message
bottle.BaseTemplate.defaults["read_form"] = read_form
bottle.BaseTemplate.defaults["logged_in_user"] = logged_in_user

if __name__ == '__main__':
    bottle.run(debug=True)