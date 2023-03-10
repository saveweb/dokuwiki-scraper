import html
import re
import urllib.parse as urlparse

import requests
from bs4 import BeautifulSoup

from dokuWikiDumper.exceptions import DispositionHeaderMissingError, HTTPStatusError


def getSourceExport(url, title, rev='', session:requests.Session=None):
    """Export the raw source of a page (at a given revision)"""

    r = session.get(url, params={'id': title, 'rev': rev, 'do': 'export_raw'})
    if r.status_code != 200:
        raise HTTPStatusError(r)
    if 'Content-Disposition' not in r.headers:
        raise DispositionHeaderMissingError(r)
    
    return r.text


def getSourceEdit(url, title, rev='', session:requests.Session=None):
    """Export the raw source of a page by scraping the edit box content. Yuck."""

    r = session.get(url, params={'id': title, 'rev': rev, 'do': 'edit'})
    soup = BeautifulSoup(r.text, 'lxml')
    return ''.join(soup.find('textarea', {'name': 'wikitext'}).text).strip()


def getRevisions(url, title, use_hidden_rev=False, select_revs=False, session:requests.Session = None):
    """ Get the revisions of a page. This is nontrivial because different versions of DokuWiki return completely different revision HTML.
    
    Returns a dict with the following keys: (None if not found or failed)
    - id: str|None
    - user: str|None
    - sum: str|None
    - date: str|None
    - minor: bool
    """
    
    use_hidden_rev = True # temp fix
    select_revs = False # temp fix
    revs = []
    rev_tmplate = {
        'id': None,
        'user': None,
        'sum': None,
        'date': None,
        'minor': False,
    }

    # if select_revs:
    if False: # disabled, it's not stable.
        r = session.get(url, params={'id': title, 'do': 'diff'})
        soup = BeautifulSoup(r.text, 'lxml')
        select = soup.find(
            'select', {
                'class': 'quickselect', 'name': 'rev2[1]'})
        for option in select.findAll('option'):
            text = option.text
            date = ' '.join(text.split(' ')[:2])
            username = len(text.split(' ')) > 2 and text.split(' ')[2]
            summary = ' '.join(text.split(' ')[3:])

            revs.append({'id': option['value'],
                        'user': username,
                        'sum': summary,
                        'date': date})

    i = 0
    continue_index = -1
    cont = True

    while cont:
        r = session.get(
            url,
            params={
                'id': title,
                'do': 'revisions',
                'first': continue_index})

        soup = BeautifulSoup(r.text, 'lxml')

        lis = soup.find('form', {'id': 'page__revisions'}).find('ul').findAll('li')

        for li in lis:
            rev = {}
            rev_hrefs = li.findAll(
                'a', href=lambda href: href and (
                    '&rev=' in href or '?rev=' in href))


            # id: optional(str(id)): rev_id, not title name.
            if rev_hrefs:
                obj1 = rev_hrefs[0]['href']
                obj2 = urlparse.urlparse(obj1).query
                obj3 = urlparse.parse_qs(obj2)
                if 'rev' in obj3:
                    rev['id'] = obj3['rev'][0]
                else:
                    rev['id'] = None
                del(obj1, obj2, obj3)

            if use_hidden_rev and 'id' in rev and rev['id'] is None:
                obj1 = li.find('input', {'type': 'hidden'})
                if obj1 is not None and 'value' in obj1:
                    rev['id'] = obj1['value']
                del(obj1)

            # minor: bool
            rev['minor'] = ('class', 'minor') in li.attrs

            # summary: optional(str)
            sum_span = li.findAll('span', {'class': 'sum'}) 
            if sum_span and not select_revs:
                sum_span = sum_span[0]
                sum_text = sum_span.text.split(' ')[1:]
                if sum_span.findAll('bdi'):
                    rev['sum'] = html.unescape(sum_span.find('bdi').text).strip()
                else:
                    rev['sum'] = html.unescape(' '.join(sum_text)).strip()
            elif not select_revs:
                print('    ', repr(li.text).replace('\\n', ' ').strip())
                wikilink1 = li.find('a', {'class': 'wikilink1'})
                text_node = wikilink1 and wikilink1.next and wikilink1.next.next or ''
                if text_node.strip:
                    rev['sum'] = html.unescape(text_node).strip(u'\u2013 \n')

            # date: optional(str)
            date_span = li.find('span', {'class': 'date'})
            if date_span:
                rev['date'] = date_span.text.strip()
            else:
                rev['date'] = ' '.join(li.text.split(' ')[:2])
                matches = re.findall(
                    r'([0-9./]+ [0-9]{1,2}:[0-9]{1,2})',
                    rev['date'])
                if matches:
                    rev['date'] = matches[0]

            # user: optional(str)
            # legacy
            # if not (select_revs and len(revs) > i and revs[i]['user']):
            user_span = li.find('span', {'class': 'user'})
            if user_span and user_span.text is not None:
                rev['user'] = html.unescape(user_span.text).strip()


            # if select_revs and len(revs) > i:
            #     revs[i].update(rev)
            # else:
            #     revs.append(rev)

            _rev = {**rev_tmplate, **rev} # merge dicts
            revs.append(_rev)

            i += 1

        # next page
        first = soup.findAll('input', {'name': 'first', 'value': True})
        continue_index = first and max(map(lambda x: x['value'], first))
        cont = soup.find('input', {'class': 'button', 'accesskey': 'n'})
        # time.sleep(1.5)

    # if revs and use_hidden_rev and not select_revs:
    #     soup2 = BeautifulSoup(session.get(url, params={'id': title}).text)
    #     revs[0]['id'] = soup2.find(
    #         'input', {
    #             'type': 'hidden', 'name': 'rev', 'value': True})['value']

    return revs