import sqlite3, bcrypt, db, os
from mutagen import mp3

conn = sqlite3.connect('music.db')
cur = conn.cursor()

user, release, song, playlist, phs = db.setup_db(conn)

def seconds_to_str(seconds):
    """
    Prevede sekunde v h:m:s
    """
    min, sec = divmod(seconds, 60)
    hour, min = divmod(min, 60)
    return '%d:%02d:%02d' % (hour, min, sec) if hour > 0 else '%02d:%02d' % (min, sec)

class AuthError(Exception):
    # Napaka pri autentikaciji
    pass

class User:
    '''
    Razred za uporabnika
    '''

    def __init__(self, id, name=None, date=None):
        if name is None or date is None:
            q = "SELECT name, date_created FROM User WHERE id = ?"
            res = conn.execute(q, [id]).fetchone()
            if res is None:
                raise ValueError("User not found")
            name, date = res
        
        self.id = id
        self.name = name
        self.date = date
        self._releases = []
        self._playlists = []

    def __str__(self):
        return self.name
    
    @property
    def releases(self):
        if not self._releases:
            self._releases = self.getReleases()
        return self._releases

    def getReleases(self, type="all"):
        if type not in ("single", "ep", "album", "all"):
            raise ValueError(f"Incorrect type {type}")
        q = "SELECT id, title, type, date_released FROM Release WHERE author = ?" + ("AND type = ?" if type != "all" else "")
        res = []
        
        for id, title, type, date in conn.execute(q, [self.id, type] if type != "all" else [self.id]):
            res.append(Release(id, self.id, title, type, date))
        return res
    
    @property
    def playlists(self):
        if not self._playlists:
            self._playlists = self.getPlaylists()
        return self._playlists
    
    def getPlaylists(self):
        q = "SELECT id, name, date_created FROM Playlist WHERE owner = ?"
        res = []
        for id, name, date in conn.execute(q, [self.id]):
            res.append(Playlist(id, self.id, name, date))
        return res

    @staticmethod
    # Vrne vpisanega uporabnika, če pravilno vnešeni podatki
    def login(name, inp_passw):
        q = "SELECT id, password FROM User WHERE name = ?;"
        res = conn.execute(q, [name]).fetchone()
        if res is None:
            raise AuthError("User not found")
        id, password = res
        if bcrypt.checkpw(inp_passw.encode('utf-8'), password.encode('utf-8')):
            return User(id)
        else:
            raise AuthError("Incorrect password")
    @staticmethod
    # Vpise novega uporabnika, ce ta ne obstaja
    def register(name, inp_pass):
        q = "SELECT id FROM User WHERE name = ?;"
        res = conn.execute(q, [name]).fetchone()
        if res is not None:
            raise AuthError("User already exists!")
        inp_pass = User.hashpw(inp_pass)
        ret = user.insert(name=name, password=inp_pass)
        return User(ret)
    
    @staticmethod
    # Vrne niz hashed gesla
    def hashpw(passw):
        return bcrypt.hashpw(passw.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        
    @staticmethod
    # Poišče uporabnike z podnizom v imenu 
    def search(query):
        q = "SELECT id, name, date_created FROM User WHERE name LIKE ?"
        res = []
        for id, name, date in conn.execute(q, [f"%{query}%"]):
            res.append(User(id, name, date))
        return res

class Song:
    '''
    Razred za pesem
    '''

    def __init__(self, id, release=None, order_num=None, title=None, length=None):
        self.id = id
        if release is None or order_num is None or title is None or length is None:
            q = "SELECT order_num, release, title, length FROM Song WHERE id = ?"
            res = conn.execute(q, [id]).fetchone()
            if res is None:
                raise ValueError("Song not found")
            order_num, release, title, length = res    
        self.order = order_num
        self.release = release
        self.title = title
        self.length = length # V sekundah
        self.location = os.path.join(".", "music",str(release),f"{order_num}.mp3")

        q = "SELECT author FROM Release WHERE id = ?"
        self.author = User(conn.execute(q, [release]).fetchone()[0])

        self.release_title = Release(release).title

    def __str__(self):
        return self.title

    @staticmethod
    # Poišče pesmi z podnizom
    def search(query):
        q = "SELECT id, order_num, release, title, length FROM Song WHERE title LIKE ?"
        res = []
        for id, order, release, title, length in conn.execute(q, [f"%{query}%"]):
            res.append(Song(id, release, order, title, length))
        return res
    
    @staticmethod
    # Doda novo pesem v tabelo pesmi, primerno premakne ter preimenuje datoteko
    def new_song(release, order_num, title, path, destination):
        length = int(mp3.MP3(path).info.length)
        os.replace(path, os.path.join(destination, str(order_num) + ".mp3"))
        song.insert(release=release, order_num=order_num, title=title, length=length)


class Release:
    '''
    Razred za izdajo
    '''

    def __init__(self, id, author=None, title=None, type=None, date=None):
        if author is None or title is None or type is None or date is None:
            q = "SELECT author, title, type, date_released FROM Release WHERE id = ?"
            res = conn.execute(q, [id]).fetchone()
            if res is None:
                raise ValueError("Release not found")
            author, title, type, date = res
        self.author = User(author)
        self.title = title
        self.type = type
        self.date = date
        self.id = id
        self._songs = []
        self._length = None
        self.location = os.path.join(".", "music",str(id))

    def __str__(self):
        return self.title

    @property
    def songs(self):
        if not self._songs:
            q = "SELECT id, order_num, title, length FROM Song WHERE release = ? ORDER BY order_num ASC"
            for id, order_num, title, length in conn.execute(q, [self.id]):
                self._songs.append(Song(id, self.id, order_num, title, length))
        return self._songs


    @property
    def length(self):
        if self._length is None:
            length = 0
            for song in self.songs:
                length += song.length
            self._length = length
        return self._length

    @staticmethod
    # Poišče izdaje z podnizom
    def search(query, qtype):
        q = "SELECT id, author, title, type, date_released FROM Release WHERE title LIKE ? AND type = ?"
        res = []
        for id, author, title, type, date in conn.execute(q, [f"%{query}%", qtype]):
            res.append(Release(id, author, title, type, date))
        return res
    
    @staticmethod
    # Doda izdajo v tabelo izdaj, zanjo ustvari datoteko
    def new_release(author, title, type, path):
        release.insert(author=author, title=title, type=type)
        q = "SELECT MAX(id), author FROM release"
        res = conn.execute(q)
        for id, _ in res:
            r_id = id
        os.mkdir(os.path.join(path, str(r_id)))
        return r_id


class Playlist:
    '''
    Razred za seznam pesmi
    '''

    def __init__(self, id, owner=None, name=None, date=None):
        if owner is None or name is None or date is None:
            q = "SELECT owner, name, date_created FROM playlist WHERE id = ?"
            res = conn.execute(q, [id])
            if res is None:
                raise ValueError("Playlist not found")
            for r in res:
                owner, name, date = r
        self.owner = User(owner)
        self.date = date
        self.name = name
        self.id = id
        self._songs = []
        self._length = None

    def __str__(self):
        return self.name

    @property
    def length(self):
        if self._length is None:
            length = 0
            for song in self.songs:
                length += song.length
            self._length = length
        return self._length

    @property
    def songs(self):
        if not self._songs:
            q = "SELECT id, release, ps.order_num, s.order_num, title, length FROM Song AS s JOIN Playlist_has_Song AS ps ON (s.id = ps.song_id) WHERE playlist_id = ? ORDER BY ps.order_num ASC"
            for id, release, p_order_num, s_order_num, title, length in conn.execute(q, [self.id]):
                self._songs.append(Song(id, release, s_order_num, title, length))
        return self._songs  

    def add_song(self, song_id):
        q = "SELECT MAX(order_num) FROM Playlist_has_song WHERE playlist_id = ? GROUP BY playlist_id"
        res = conn.execute(q, [self.id])
        order_num = 1
        for r in res:
            order_num = r + 1
        phs.insert(playlist_id=self.id, song_id=song_id, order_num=order_num)

    @staticmethod
    def create(owner, name):
        return playlist.insert(owner=owner, name=name)
