#!/usr/bin/env python
from __future__ import print_function, absolute_import, division
import sys
reload(sys); sys.setdefaultencoding("utf-8")
import logging

from collections import defaultdict
from errno import ENOENT
from stat import S_IFDIR, S_IFLNK, S_IFREG
from time import time

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn


import xmlrpclib

if not hasattr(__builtins__, 'bytes'):
	bytes = str

class Xmlrpcstore(object):
	def __init__(self, url, username, password, verbose=False):
		self.server = xmlrpclib.Server(url, verbose=verbose)
		self.username = username
		self.password = password
	def get_posts(self):
		return self.server.wp.getPosts(0, self.username, self.password, {'post_type': 'page'})
	def edit_post(self, post_id, data):
		return self.server.wp.editPost(0, self.username, self.password, post_id, data)

class Node(object):
	def __init__(self):
		pass

class RootNode(Node):
	def __init__(self):
		pass
	def readdir(self, path, fh=None):
		pass
	def getattr(self, path, fh=None):
		pass

class PostNode(Node):
	def __init__(self):
		pass
	def read(self, path, size, offset, fh):
		pass
	def getattr(self, path, fh=None):
		pass
	def write(self, path, data, offset, fh):
		pass
	def truncate(self, path, length, fh=None):
		pass

class IndexNode(Node):
	def __init__(self):
		pass
	def read(self, path, size, offset, fh):
		pass
	def getattr(self, path, fh=None):
		pass
	def write(self, path, data, offset, fh):
		pass
	def truncate(self, path, length, fh=None):
		pass


class VFS(object):
	def __init__(self, url, username, password):
		self.store = Xmlrpcstore(url, username, password)
		self.fd = 0
		self.ago = time()
		# self.dircache = None
		self.postcache = None
	def build_post_file(self, title, content=None):
		if content is None:
			return title
		return "\n\n".join((title, content))+"\n"
	def parse_post_file(self, file_content):
		parts = file_content.split("\n", 1)
		title = parts[0]
		if len(parts) == 1:
			content = ""
		else:
			content = parts[1]
			if content.startswith("\n"):
				content = content[1:]
		return (title, content)
	def invalidate_cache(self):
		self.postcache = None
	def get_posts(self):
		if not self.postcache:
			# self.postcache = self.server.wp.getPosts(0, self.user, self.password, {'post_type': 'page'})
			self.postcache = self.store.get_posts()
		# print(self.postcache)
		return self.postcache
	def get_post_ids(self):
		posts = self.get_posts()
		return [int(post["post_id"]) for post in posts]
	def get_post(self, idx):
		posts = self.get_posts()
		for post in posts:
			if str(post["post_id"]) == str(idx):
				return post
	def readdir(self, path, fh=None):
		return ['.', '..'] + [str(i) for i in self.get_post_ids()]
	def get_content(self, path):
		post = self.get_post(path.lstrip("/"))
		content = post["post_content"]
		return content
	def get_title(self, path):
		post = self.get_post(path.lstrip("/"))
		title = post["post_title"]
		return title
	def get_post_file_content(self, path):
		post = self.get_post(path.lstrip("/"))
		title = post["post_title"]
		content = post["post_content"]
		return self.build_post_file(title, content)
	def read(self, path, size, offset, fh):
		if not self.file_exists(path):
			raise FuseOSError(ENOENT)
		file_content = self.get_post_file_content(path)
		# print(content)
		return file_content.encode("utf-8")[offset:offset + size]
	def file_exists(self, path):
		if path == "/":
			return True
		lst = self.readdir(self, path)
		return path.lstrip("/") in lst
	def getattr(self, path, fh=None):
		if not self.file_exists(path):
			raise FuseOSError(ENOENT)
		mode = 0o700
		if path == "/":
			return dict(
			st_mode=(S_IFDIR | 0o755),
			st_ctime=self.ago,
			st_mtime=self.ago,
			st_atime=self.ago,
			st_nlink=2)
		return dict(
			st_mode=(S_IFREG | mode),
			st_nlink=1,
			st_size=len(self.get_post_file_content(path).encode("utf-8")),
			st_ctime=self.ago,
			st_mtime=self.ago,
			st_atime=self.ago)	
	def put_content(self, path, content):
		post_id = path.lstrip("/")
		# result = self.server.wp.editPost(0, self.user, self.password, post_id, {'post_content': content})
		result = self.store.edit_post({'post_content': content})
	def put_post(self, path, title, content):
		post_id = path.lstrip("/")
		# result = self.server.wp.editPost(0, self.user, self.password, post_id, {'post_title': title, 'post_content': content})
		result = self.store.edit_post({'post_title': title, 'post_content': content})
	def write(self, path, data, offset, fh):
		file_content = self.get_post_file_content(path)
		new_content = file_content.encode("utf-8")[:offset] + data
		title, content = self.parse_post_file(new_content)
		self.put_post(path, title, content)
		self.invalidate_cache()
		return len(data)
	def truncate(self, path, length, fh=None):
		file_content = self.get_post_file_content(path)
		new_content = file_content.encode("utf-8")[:length]
		title, content = self.parse_post_file(new_content)
		self.put_post(path, title, content)
		self.invalidate_cache()

		

	
	


class Wordpress(LoggingMixIn, Operations):
	'Example memory filesystem. Supports only one level of files.'

	def __init__(self, url, username, password):
		self.files = {}
		self.data = defaultdict(bytes)
		self.fd = 0
		now = time()
		self.files['/'] = dict(
			st_mode=(S_IFDIR | 0o755),
			st_ctime=now,
			st_mtime=now,
			st_atime=now,
			st_nlink=2)
		self.vfs = VFS(url, username, password)

	def chmod(self, path, mode):
		return 0

	def chown(self, path, uid, gid):
		pass

	def create(self, path, mode):
		self.files[path] = dict(
			st_mode=(S_IFREG | mode),
			st_nlink=1,
			st_size=0,
			st_ctime=time(),
			st_mtime=time(),
			st_atime=time())

		self.fd += 1
		return self.fd

	def getattr(self, path, fh=None):
		return self.vfs.getattr(path)

	def getxattr(self, path, name, position=0):
		return '' 
		raise FuseOSError(ENOATTR)
		"""

		attrs = self.files[path].get('attrs', {})

		try:
			return attrs[name]
		except KeyError:
			return ''	   # Should return ENOATTR
		"""

	def listxattr(self, path):
		return []
		"""
		attrs = self.files[path].get('attrs', {})
		return attrs.keys()
		"""

	def mkdir(self, path, mode):
		pass

	def open(self, path, flags):
		self.fd += 1
		return self.fd

	def read(self, path, size, offset, fh):
		return self.vfs.read(path, size, offset, fh)

	def readdir(self, path, fh):
		return self.vfs.readdir(path)

	def readlink(self, path):
		return self.data[path]

	def removexattr(self, path, name):
		attrs = self.files[path].get('attrs', {})

		try:
			del attrs[name]
		except KeyError:
			pass		# Should return ENOATTR

	def rename(self, old, new):
		pass

	def rmdir(self, path):
		pass

	def setxattr(self, path, name, value, options, position=0):
		pass

	def statfs(self, path):
		return dict(f_bsize=512, f_blocks=4096, f_bavail=2048)

	def symlink(self, target, source):
		pass

	def truncate(self, path, length, fh=None):
		# self.data[path] = self.data[path][:length]
		# self.files[path]['st_size'] = length
		return self.vfs.truncate(path, length, fh)

	def unlink(self, path):
		pass

	def utimens(self, path, times=None):
		pass

	def write(self, path, data, offset, fh):
		return self.vfs.write(path, data, offset, fh)
		# self.data[path] = self.data[path][:offset] + data
		# self.files[path]['st_size'] = len(self.data[path])
		# return len(data)


if __name__ == '__main__':
	import argparse
        import urlparse
	parser = argparse.ArgumentParser()
	parser.add_argument('url', help="blog url")
	parser.add_argument('mountpoint', help="mountpoint")
        parser.add_argument('-u', dest="username", help="username")
        parser.add_argument('-p', dest="password", help="password")
        parser.add_argument('-n', dest="noappend", help="do not append /xmlrpc.php to url")
	args = parser.parse_args()

        parsed_url = urlparse.urlparse(args.url)
        url = urlparse.urlunparse(parsed_url[:6])
        if not args.noappend:
            url = urlparse.urljoin(url, "xmlrpc.php")

        if args.username:
            username = args.username
        elif parsed_url.username:
            username = parsed_url.username
        else:
            username = input('Enter username: ')

        if args.password:
            password = args.password
        elif parsed_url.password:
            password = parsed_url.password
        else:
            password = input('Enter password: ')


	logging.basicConfig(level=logging.DEBUG)
	fuse = FUSE(Wordpress(url, username, password), args.mountpoint, foreground=True, allow_other=False)
