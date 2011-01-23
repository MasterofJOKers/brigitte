# -*- coding: utf-8 -*-
import re
from lxml import etree
from datetime import datetime
from django.conf import settings

from brigitte.repositories.backends.base import BaseCommit, BaseRepo, BaseTag

FILETYPE_MAP = getattr(settings, 'FILETYPE_MAP', {})

class Repo(BaseRepo):
    def get_recent_commits(self, sha=None, count=10):
        if sha == None:
            sha = 'HEAD'

        cmd = ['git',
            '--git-dir=%s' % self.path,
            'log',
            '--no-color',
            '--raw',
            '--pretty=format:\
                <commit>\
                    <timestamp>%ct</timestamp>\
                    <ago>%cr</ago>\
                    <short_msg><![CDATA[%s]]></short_msg>\
                    <committer><![CDATA[%cn]]></committer>\
                    <committer_mail><![CDATA[%ce]]></committer_mail>\
                    <committer_time_iso>%cd</committer_time_iso>\
                    <committer_timestamp>%ct</committer_timestamp>\
                    <author><![CDATA[%an]]></author><author_mail>\
                    <![CDATA[%ae]]></author_mail>\
                    <author_time_iso>%ad</author_time_iso>\
                    <author_timestamp>%at</author_timestamp>\
                    <id>%H</id>\
                    <short_id>%h</short_id>\
                    <parent>%P</parent>\
                    <short_parent>%p</short_parent>\
                    <tree>%T</tree>\
                    <short_tree>%t</short_tree>\
                    <msg><![CDATA[%B]]></msg>\
                </commit>',
            sha,
            '-'+str(count)
        ]

        commits = []
        try:
            outp = '<?xml version="1.0" encoding="UTF-8"?><log>' \
                + self.syswrapper(cmd) + '</log>'

            log = etree.XML(outp)

            for commit in log.iterchildren():
                c = {}
                for field in commit.iterchildren():
                    if field.text:
                        c[field.tag] = field.text.strip()
                commits.append(Commit(self.path, c))
        except:
            pass

        return commits

    def get_commit(self, sha):
        try:
            return self.get_recent_commits(sha, 1)[0]
        except IndexError:
            pass
        return None

    def get_last_commit(self):
        return self.get_commit(None)

    def get_tags(self):
        cmd = ['git',
            '--git-dir=%s' % self.path,
            'tag']
        tags = self.syswrapper(cmd).strip().split('\n')
        tags.reverse()
        outp = []
        for tag in tags:
            if len(tag) > 0:
                outp.append(Tag(self.path, tag))
        return outp

    def init_repo(self):
        cmd = ['git',
               'init',
               '--bare',
               self.path]
        self.syswrapper(cmd)
        return True

class Tag(BaseTag):
    def __repr__(self):
        return '<Tag: %s>' % self.name


class Commit(BaseCommit):
    def __repr__(self):
        return '<Commit: %s>' % self.id

    @property
    def parents(self):
        return self.parent.split(' ')

    @property
    def short_parents(self):
        return [parent[:7] for parent in self.parents]

    @property
    def both_parents(self):
        return [(parent[:7], parent) for parent in self.parents]

    @property
    def changed_files(self):
        cmd = ['git',
            '--git-dir=%s' % self.path,
            'log',
            '-1',
            '--numstat',
            '--pretty=format:',
            str(self.id),
        ]

        diff_output = self.syswrapper(cmd).strip()
        files = []
        for line in [l for l in diff_output.split('\n') if len(l) > 0]:
            files.append(line.split('\t'))

        return files

    @property
    def diff(self):
        cmd = ['git',
            '--git-dir=%s' % self.path,
            'diff-tree',
            '-p',
            str(self.id)]
        return self.syswrapper(cmd)


    def get_tree(self, path):
        regex = re.compile(
            "(?P<rights>\d*)\s(?P<type>[a-z]*)"\
            "\s(?P<sha>\w*)\s*(?P<size>[0-9 -]*)\s*(?P<path>.+)")

        if not path:
            path = ''
        else:
            if not path[-1] == '/':
                path = path+'/'

        cmd = ['git',
            '--git-dir=%s' % self.path,
            'ls-tree',
            '-l',
            str(self.id),
            path]


        fileregex = re.compile("\.\w+")
        try:
            treedir = []
            outp = self.syswrapper(cmd)
            if outp.strip():
                for treefile in outp.strip().split('\n'):
                    r = regex.search(treefile)
                    tfile = r.groupdict()
                    tfile['name'] = tfile['path'].rsplit('/', 1)[-1]
                    if tfile['type'] == 'tree':
                        tfile['path'] += '/'
                    else:
                        if not fileregex.match(tfile['name']):
                            if '.' in tfile['name']:
                                tfile['suffix'] = tfile['name'].rsplit('.', 1)[-1]
                                tfile['mime_image'] = FILETYPE_MAP.get(tfile['suffix'], FILETYPE_MAP['default'])
                            else:
                                tfile['suffix'] = ''
                                tfile['mime_image'] = FILETYPE_MAP['default']
                        else:
                            tfile['suffix'] = ''
                            tfile['mime_image'] = FILETYPE_MAP['default']

                    treedir.append(tfile)
            return {
                'path': path,
                'tree': treedir
            }
        except:
            return None

    def get_file(self, path):
        cmd = ['git',
            '--git-dir=%s' % self.path,
            'show',
            '--exit-code',
            '%s:%s' % (self.id, path)]

        try:
            outp = self.syswrapper(cmd)
            return outp
        except:
            return None

    @property
    def commit_date(self):
        return datetime.fromtimestamp(float(self.timestamp))
