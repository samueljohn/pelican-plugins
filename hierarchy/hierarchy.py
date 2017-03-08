# -*- coding: utf-8 -*-

"""
hierarchy -- provides hierarchical organization of pages.

Copyright © 2014 Samuel John (www.SamuelJohn.de)

The MIT License (MIT)
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the “Software”), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

import os
import logging
from collections import OrderedDict

from pelican import signals, contents, generators, utils, readers

__version__ = (0, 1, 2)

# Tweak the Pelican logger to also show the `name` of the logger.
logger = logging.getLogger("hierarchy")
logger.parent.handlers[-1].formatter._style._fmt = \
    '%(customlevelname)s %(name)s - %(message)s'

STATIC_EXTENSIONS = ('png', 'jpeg', 'jpg', 'gif', 'tif', 'tiff',
                     'doc', 'docx', 'xls',
                     'pdf',
                     'zip', 'tar', 'gz',
                     'js')

FILENAME_METADATA = r'(?P<order>[0-9]*(_|-| ))?(?P<title>((?!-(en|de)).)+)(-(?P<lang>(en|de)))?'
HIPAGE_URL = HIPAGE_SAVE_AS = "{hierarchy}.html"
HIPAGE_LANG_URL = HIPAGE_LANG_SAVE_AS = "{hierarchy}-{lang}.html"



def ascii_tree(tree, print_item=repr, prefix=[], last_prefix=""):
    """
    Print a nice ASCII tree of the iterable `tree`.

    To print each item, the `print_item` callable is used and has to
    return a `str`.
    """
    s = "".join(prefix[:-1]) + last_prefix + print_item(tree) + "\n"
    try:
        last_i = len(tree) - 1
        for i, item in enumerate(tree):
            if i == last_i:
                s += ascii_tree(item,
                                prefix=prefix + ["    "],
                                last_prefix="└── ",
                                print_item=print_item)
            else:
                s += ascii_tree(item,
                                prefix=prefix + ["│   "],
                                last_prefix="├── ",
                                print_item=print_item)
    except TypeError:
        pass
    return s


class CopyStaticAssetsGenerator(generators.Generator):

    """Copy files (with certain extensions) to the `output_path`."""

    def generate_output(self, writer):
        self._generate_output_for(writer, 'ARTICLE')
        self._generate_output_for(writer, 'PAGE')

    def _generate_output_for(self, writer, kind):
        extensions = STATIC_EXTENSIONS
        if STATIC_EXTENSIONS in self.settings:
            extensions.extend(self.settings['STATIC_EXTENSIONS'])
            extensions.extend([ext.upper() for ext in STATIC_EXTENSIONS]])

        for f in self.get_files(
                self.settings[kind + '_PATHS'],
                exclude=self.settings[kind + '_EXCLUDES'],
                extensions=extensions):
            # hack, remove "pages/" and put the HiPages directly
            # in the root, instead
            t = f
            if f.startswith("pages/"):
                t = f.split("pages/")[1]
            utils.copy(os.path.join(self.path, f),
                       os.path.join(self.output_path, t))

# todo: Add the filenames of the assests to the url list in context
#       so that _update_content can fix relative URLs
# overwrite with Title if a page exists

# If there is dir in PAGE_DIR, then create an output dir
# and add an index.html (unless there is an index.md)

# Todo: Submit a PR to Pelican to allow cleanly replaceing PagesGenerator.
#       This is currently not possible, because in `__init__.py` in the method
#       `run` there is only a local variable `generators` that is not
#       available to any signal.


class HiPage(contents.Page):

    """
    HiPage inherits from `Page` and implements a hierarchical organization.

    There are the properties `parent` and `level` to access the hierarchy.
    A HiPage page re-uses the page template of Pelican. Because the `slug` is
    used by Pelican as a kind of unique id for pages (e.g. for finding
    translations), we set the slug to the relative path

    A HiPage is iterable to go over all (direct) `sub_pages`. It also supports
    the `__contains__` method based on the `name`, so that
        if "foobar" in page
    works by checking if a page with `name` "foobar" is among the sub_pages
    of this page.
    Under the hood, the hierarchy is implemented as an OrderedDict
    in the property `sub_pages`, where the `name`s are the keys to the mapping.
    If you need to add sub pages, you'll have to work directly with the
    `sub_pages` OrderedDict.
    """

    def __init__(self, content, metadata=None, settings=None,
                 source_path=None, context=None, slug=None, name=None,
                 title=None, parent=None, virtual=False, **kws):
        self.parent = parent
        self.sub_pages = OrderedDict()
        self.order = ""
        self.virtual = virtual

        logger.debug("New HiPage object created:")

        if source_path is None:
            assert name is not None,\
                "If no `source_path` given, a name is needed."
            assert title is not None,\
                "If no `source_path` given, a title is needed."
            assert slug is not None,\
                "If no `source_path` given, a slug is needed."
        else:
            m = readers.parse_path_metadata(
                source_path,
                settings={'FILENAME_METADATA': FILENAME_METADATA})
            if 'order' in m and m['order'] is not None:
                self.order = m['order']
            self.name = self.order + utils.slugify(m['title'])
            self.title = m['title']

        super(HiPage, self).__init__(content,
                                     metadata=metadata,
                                     settings=settings,
                                     source_path=source_path,
                                     context=context,
                                     **kws)

        # This is to work around a Pelican bug that a FILENAME_METADATA regex
        # group can be empty which results in lang being `None`.
        if hasattr(self, 'lang'):
            if self.lang is None:
                self.lang = settings['DEFAULT_LANG']
                self.in_default_lang = True

        # If title, slug or name are given as keywords, then, we overwrite
        # what the super constructor set.
        if name is not None:
            self.name = self.order + utils.slugify(name)
            logger.debug("    name='{0}' was explicitly given.".
                         format(name))

        if slug is not None:
            # don't slugify here because we need it to be ../index.html later
            self._slug = slug
            logger.debug("    slug='{0}' was explicitly given.".
                         format(slug))
        else:
            self._slug = None

        if title is not None:
            self.title = title
            logger.debug("    title='{0}' was explicitly given.".
                         format(title))

        logger.debug("    (name={0}, title={1}, slug={2}, lang={3})".
                     format(self.name, self.title, self.slug, self.lang))

    @property
    def slug(self):
        if self._slug is not None:
            return self._slug
        else:
            s = [p.name for p in self.hierarchy if p.parent] + [self.name]
            return ">".join(s)

    @slug.setter
    def slug(self, value):
        self._slug = value

    def __iter__(self):
        # The "iter" around is necessary because Jinja cannot yet handle
        # a ValuesView :-/
        return iter(self.sub_pages.values())

    def __contains__(self, item):
        if isinstance(item, contents.Page):
            item = item.name
        return True if item in self.sub_pages else False

    def __getitem__(self, key):
        return self.sub_pages[key]

    def __len__(self):
        return len(self.sub_pages)

    @property
    def has_children(self):
        return bool(len(self))

    @property
    def hierarchy(self):
        """Generator giving pages, from self.parent upwards to root."""
        up = self.parent
        while up is not None:
            yield up
            up = up.parent

    @property
    def level(self):
        """The level (depth) in the hierarchy. The virtual root page has 0."""
        return len(list(self.hierarchy))

    @property
    def breadcrumps(self):
        """Returning tuples `(url, title)` from root to this page."""
        bc = []  # (self.url, self.title)]
        for p in self.hierarchy:
            if p.parent:
                bc.append((p.url, p.title))
        return reversed(bc)

    @property
    def url_format(self):
        """
        Add the `hierarchy` entry to the metadata for url and save_as
        expansion.
        """
        metadata = getattr(super(HiPage, self), "url_format")
        hi = "/".join(list(reversed([p.name for p in self.hierarchy
                                     if p.parent])) +
                      [self.name])
        metadata.update({'hierarchy': hi, 'name': self.name})
        return metadata

    def __hash__(self):
        """Ignoring the self.sub_pages and just make HiPage hashable."""
        return object.__hash__(self)

    def __repr__(self):
        return "<{cl} {url}>".format(cl=self.__class__.__name__, url=self.url)

    def print_tree(self):
        print(ascii_tree(self, print_item=lambda x: x.title))


class HiPagesGenerator(generators.PagesGenerator):

    """
    Generate hierarchically arranged pages (of class `HiPage`).

    This class can replace `generator.PagesGenerator`.
    """

    def __init__(self, *args, **kws):
        super(HiPagesGenerator, self).__init__(*args, **kws)

    def generate_context(self):
        """
        Overwrites `PagesGenerator.generate_context` and builds up `HiPage`s.
        """
        root = HiPage("", slug='../index', name="index", title='Home',
                      parent=None, settings=self.settings)
        all_pages = []
        hidden_pages = []

        for page_path in self.settings['PAGE_PATHS']:
            ps, hs = self._scan_dir_r(
                os.path.join(self.path, page_path),
                exclude=self.settings['PAGE_EXCLUDES'],
                parent=root)
            all_pages.extend(ps)
            hidden_pages.extend(hs)

        self.pages, self.translations = utils.process_translations(all_pages)
        self.hidden_pages, self.hidden_translations = (
            utils.process_translations(hidden_pages))
        self.PAGES_TREE = root

        # Fix (hack): Go through all translations and add the missing sub-pages
        for page in self.translations:
            # find corresponding page
            orig_page = None
            for p in self.pages:
                if p.name == page.name:
                    orig_page = p
                    break
            page.sub_pages.update(orig_page.sub_pages)

        self._update_context(['pages', 'hidden_pages', 'PAGES_TREE'])
        # self.context['PAGES'] = self.pages
        # self.context['PAGES_TREE'] = root
        logger.info("\n" + ascii_tree(self.context['PAGES_TREE'],
                                      print_item=lambda x: x.title))

        signals.page_generator_finalized.send(self)

    def _scan_dir_r(self, base_path, rel_path="",
                    exclude=None, parent=None, extensions=None):
        """
        Recursively scan `base_path/rel_path` for source files.

        Symlinks are followed.

        `base_path`: Absolute directory path (`str`).
        `rel_path`: The relative dir below `base_path` to start scanning.
        `exclude`: Directory names to exclude.
        `parent`: The `HiPage` that is used as the parent for items in `path`.
        """
        pages = []
        hidden_pages = []
        path = os.path.join(base_path, rel_path)

        for item in sorted(os.listdir(path)):
            # Get the path to the `item` relative to the base_path
            abs_item = os.path.join(path, item)
            rel_item = os.path.join(os.path.relpath(path, base_path), item)
            logger.debug("Scanning {}".format(rel_item))

            if os.path.isfile(abs_item):
                # Using the include logic from parent class:
                if not self._include_path(rel_item, extensions):
                    logger.debug("... skipping {} (unknown extension)".
                                 format(rel_item))
                    continue

                try:
                    page = self.readers.read_file(
                        base_path=base_path,
                        path=rel_item,
                        content_class=HiPage,
                        context=self.context,
                        preread_signal=signals.page_generator_preread,
                        preread_sender=self,
                        context_signal=signals.page_generator_context,
                        context_sender=self)
                except Exception as e:
                    logger.warning('could not process {}\n{}'
                                   .format(rel_item, e))
                    continue

                if not contents.is_valid_content(page, rel_item):
                    logger.warn('invalid content for ' + rel_item)
                    continue

                self.add_source_path(page)

                if page.name in parent.sub_pages.keys():
                    old_page = parent.sub_pages[page.name]
                    if old_page.virtual:
                        # Instead of the virtual page use the parents's one
                        logger.debug("replace a virtual HiPage by this " +
                                     repr(page))
                        for sub in parent.sub_pages[page.name]:
                            page.sub_pages[sub.name] = sub
                            sub.parent = page
                        pages.remove(parent.sub_pages[page.name])
                        del parent.sub_pages[page.name]
                    elif page.in_default_lang:
                        # if this page is in_default_lang then we just replace
                        # the old_page in the tree but not in `pages`:
                        for sub in old_page:
                            page.sub_pages[sub.name] = sub
                            sub.parent = page
                        del parent.sub_pages[page.name]

                if page.status == "published":
                    pages.append(page)
                    page.parent = parent
                    if page.in_default_lang:
                        # Always adding the page if it is in the default lang,
                        # possibly overwriting an older assignment from a
                        # translated page that happend to be processed before:
                        parent.sub_pages[page.name] = page
                    elif page.name not in parent:
                        # Only add a translation to the parent, if there is
                        # not already a page with the same name in parent:
                        parent.sub_pages[page.name] = page
                    else:
                        logger.warn(parent.name + " has already another "
                                    "entry for " + page.name)

                elif page.status == "hidden":
                    # Don't add hidden pages to the parent. They are still
                    # there but not in the `sub_pages` dict of parent.
                    hidden_pages.append(page)
                elif page.status == "draft":
                    pages.append(page)
                else:
                    logger.warning("Unknown status '%s' for file %s, "
                                   "skipping it." %
                                   (repr(page.status), repr(rel_item)))

            elif os.path.isdir(abs_item):

                if item in exclude:
                    continue

                # Virtual page, that is used when there is not already a page
                # with the same name under the current `parent`.
                m = readers.parse_path_metadata(
                    rel_item,
                    settings={'FILENAME_METADATA': FILENAME_METADATA})

                page = HiPage("", virtual=True,
                              source_path=item,
                              parent=parent,
                              metadata=m,
                              settings=self.settings)

                # Because we allow to override the HiPage for a directory
                # `foo` by providing a `foo.md` file, we check now whether the
                # file already exists, or an empty `HiPage` should be created
                # for this directory.
                logger.debug("is a dir -> name={0}, lang={1}, slug={2}".
                             format(page.name, page.lang, page.slug))
                if page.name in parent.sub_pages.keys():
                    # Instead of the virtual page use the parents's one
                    logger.debug("    ... ignored because Parent has {0} in "
                                 "its sub_pages: {1}".
                                 format(repr(parent), repr(parent.sub_pages)))
                    page = parent.sub_pages[page.name]
                else:
                    # Add the virtual page (created above) to the parent
                    logger.debug("    ... as a virtual page: " + page.name)
                    parent.sub_pages[page.name] = page

                self.add_source_path(page)
                pages.append(page)

                # Recursively descent into the directory
                ps, hs = self._scan_dir_r(base_path=base_path,
                                          rel_path=rel_item,
                                          exclude=exclude,
                                          parent=page)
                pages.extend(ps)
                hidden_pages.extend(hs)

            else:
                raise Exception("not a dir and not a file")  # possible at all?
        logger.debug("---------------")

        return pages, hidden_pages


def remove_normal_pages(self):
    """This is a hack to keep Pelican from generating the normal Pages."""
    if self.__class__ == generators.PagesGenerator:
        def noop(self, *args, **kws):
            logger.debug("Dummy `noop` called instead of "
                         "`get_files` to replace `Page` by `HiPage`.")
            return []
        # The easiest way, I found, was just to make `get_files` a noop.
        self.get_files = noop
        logger.warn("`get_files()` of "
                    + self.__class__.__name__ +
                    " disabled in favor of `HiPagesGenerator`.")


def add_hi_pages_generator(self):
    return HiPagesGenerator


def add_copy_statics_generator(self):
    return CopyStaticAssetsGenerator


def update_settings(pelican):
    logger.info("Updating pelican settings for HIPAGE_...URL/SAVE_AS")
    pelican.settings['HIPAGE_URL'] = HIPAGE_URL
    pelican.settings['HIPAGE_LANG_URL'] = HIPAGE_LANG_URL
    pelican.settings['HIPAGE_SAVE_AS'] = HIPAGE_SAVE_AS
    pelican.settings['HIPAGE_LANG_SAVE_AS'] = HIPAGE_LANG_SAVE_AS


def register():
    """
    The entry point for Pelican plugins.

    A pelican plugin has to have this function. We cannot directly give the
    class but a callable, which returns the class, is needed.
    """
    signals.get_generators.connect(add_hi_pages_generator)
    signals.get_generators.connect(add_copy_statics_generator)
    signals.page_generator_init.connect(remove_normal_pages)
    signals.initialized.connect(update_settings)
