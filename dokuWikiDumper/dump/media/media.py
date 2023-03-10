import os
import re
import urllib.parse as urlparse

from bs4 import BeautifulSoup

from dokuWikiDumper.utils.util import smkdir, uopen


def getFiles(url, ns:str = '',  dumpDir:str = '', session=None):
    """ Return a list of media filenames of a wiki """

    if dumpDir and os.path.exists(dumpDir + '/dumpMeta/files.txt'):
        with uopen(dumpDir + '/dumpMeta/files.txt', 'r') as f:
            files = f.read().splitlines()
            if files[-1] == '--END--':
                print('Loaded %d files from %s' % (len(files) - 1, dumpDir + '/dumpMeta/files.txt'))
                return files[:-1] # remove '--END--'

    files = set()
    ajax = urlparse.urljoin(url, 'lib/exe/ajax.php')
    medialist = BeautifulSoup(
        session.post(ajax, {
            'call': 'medialist',
            'ns': ns,
            'do': 'media'
        }).text, 'lxml')
    medians = BeautifulSoup(
        session.post(ajax, {
            'call': 'medians',
            'ns': ns,
            'do': 'media'
        }).text, 'lxml')
    imagelinks = medialist.findAll(
        'a',
        href=lambda x: x and re.findall(
            '[?&](media|image)=',
            x))
    for a in imagelinks:
        query = urlparse.parse_qs(urlparse.urlparse(a['href']).query)
        key = 'media' if 'media' in query else 'image'
        files.add(query[key][0])
    files = list(files)
    namespacelinks = medians.findAll('a', {'class': 'idx_dir', 'href': True})
    for a in namespacelinks:
        query = urlparse.parse_qs(urlparse.urlparse(a['href']).query)
        files += getFiles(url, query['ns'][0], session=session)
    print('Found %d files in namespace %s' % (len(files), ns or '(all)'))

    if dumpDir:
        smkdir(dumpDir + '/dumpMeta')
        with uopen(dumpDir + '/dumpMeta/files.txt', 'w') as f:
            f.write('\n'.join(files))
            f.write('\n--END--\n')

    return files


def dumpMedia(url: str = '', dumpDir: str = '', session=None):
    if not dumpDir:
        raise ValueError('dumpDir must be set')
    prefix = dumpDir
    smkdir(prefix + '/media')
    smkdir(prefix + '/media_attic')
    smkdir(prefix + '/media_meta')

    fetch = urlparse.urljoin(url, 'lib/exe/fetch.php')

    files = getFiles(url, dumpDir=dumpDir, session=session)
    for title in files:
        titleparts = title.split(':')
        for i in range(len(titleparts)):
            dir = "/".join(titleparts[:i])
            smkdir(prefix + '/media/' + dir)
        with open(prefix + '/media/' + title.replace(':', '/'), 'wb') as f:
            # open in binary mode
            f.write(session.get(fetch, params={'media': title}).content)
        print('File %s' % title)
        # time.sleep(1.5)
