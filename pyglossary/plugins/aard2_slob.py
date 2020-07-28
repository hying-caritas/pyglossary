# -*- coding: utf-8 -*-

from formats_common import *

enable = True
format = 'Aard2Slob'
description = 'Aard 2 (slob)'
extensions = ('.slob',)
singleFile = True
tools = [
	{
		"name": "Aard 2 for Android",
		"web": "http://aarddict.org/",
		"platforms": ["Android"],
		"license": "GPL",
		# no auto-RTL (in plaintext or html)
	},
	{
		"name": "Aard2 for Web",
		"web": "http://aarddict.org/",
		"platforms": ["Web"],
		"license": "MPL",
		# auto-RTL works in plaintext mode, but not html
	},
]
optionsProp = {
	"compression": StrOption(
		values=["", "bz2", "zlib", "lzma2"],
		comment="Compression Algorithm",
	),
	"content_type": StrOption(
		customValue=True,
		values=[
			"text/plain; charset=utf-8",
			"text/html; charset=utf-8",
		],
		comment="Content Type",
	),
	"encoding": EncodingOption(),
}
depends = {
	"icu": "PyICU",
}


class Reader(object):
	def __init__(self, glos):
		self._glos = glos
		self._clear()
		self._re_bword = re.compile(
			'(<a href=[^<>]+?>)',
			re.I,
		)
		try:
			import icu
		except ModuleNotFoundError as e:
			e.msg += f", run `{pip} install PyICU` to install"
			raise e

	def close(self):
		if self._slobObj is not None:
			self._slobObj.close()
		self._clear()

	def _clear(self):
		self._filename = ""
		self._slobObj = None  # slobObj is instance of slob.Slob class

	def open(self, filename, encoding="utf-8"):
		from pyglossary.plugin_lib import slob
		self._filename = filename
		self._slobObj = slob.open(filename)

	def __len__(self):
		if self._slobObj is None:
			log.error("called len() on a reader which is not open")
			return 0
		return len(self._slobObj)

	def _href_sub(self, m: re.Match) -> str:
		st = m.group(0)
		if "//" in st:
			return st
		st = st.replace('href="', 'href="bword://')
		st = st.replace("href='", "href='bword://")
		return st

	def __iter__(self):
		from pyglossary.plugin_lib.slob import MIME_HTML, MIME_TEXT
		if not self._slobObj:
			log.error("iterating over a reader which is not open")
			return

		slobObj = self._slobObj
		blobSet = set()

		# slob library gives duplicate blobs when iterating over slobObj
		# even keeping the last id is not enough, since duplicate blobs
		# are not all consecutive. so we have to keep a set of blob IDs

		for blob in slobObj:
			_id = blob.id
			if _id in blobSet:
				yield None  # update progressbar
				continue
			blobSet.add(_id)

			# blob.key is str, blob.content is bytes
			word = blob.key

			ctype = blob.content_type.split(";")[0]
			if ctype not in (MIME_HTML, MIME_TEXT):
				log.debug(f"{word!r}: content_type={blob.content_type}")
				if word.startswith("~/"):
					word = word[2:]
				yield self._glos.newDataEntry(word, blob.content)
				continue
			defiFormat = ""
			if ctype == MIME_HTML:
				defiFormat = "h"
			elif ctype == MIME_TEXT:
				defiFormat = "m"

			defi = blob.content.decode("utf-8")
			defi = self._re_bword.sub(self._href_sub, defi)
			yield self._glos.newEntry(word, defi, defiFormat=defiFormat)


class Writer(object):
	def __init__(self, glos: GlossaryType) -> None:
		self._glos = glos

	def write(
		self,
		filename: str,
		compression: str = "",
		content_type: str = "",
	) -> Generator[None, "BaseEntry", None]:
		try:
			import icu
		except ModuleNotFoundError as e:
			e.msg += f", run `{pip} install PyICU` to install"
			raise e
		from pyglossary.plugin_lib import slob
		glos = self._glos
		kwargs = {}
		if compression:
			kwargs["compression"] = compression
		# must not pass compression=None to slob.create()
		with slob.create(filename, **kwargs) as slobWriter:
			name = glos.getInfo("name")
			slobWriter.tag("label", toStr(name))
			while True:
				entry = yield
				if entry is None:
					break
				words = entry.l_word
				b_defi = entry.defi.encode("utf-8")
				_ctype = content_type
				if not _ctype:
					entry.detectDefiFormat()
					defiFormat = entry.defiFormat
					if defiFormat == "h":
						_ctype = "text/html; charset=utf-8"
						b_defi = b_defi.replace(b'"bword://', b'"')
						b_defi = b_defi.replace(b"'bword://", b"'")
					elif defiFormat == "m":
						_ctype = "text/plain; charset=utf-8"
					else:
						_ctype = "text/plain; charset=utf-8"
				slobWriter.add(
					b_defi,
					*tuple(words),
					content_type=_ctype,
				)
		# slobWriter.finalize() is called called on __exit__
