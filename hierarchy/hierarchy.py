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
from copy import copy
from collections import OrderedDict
import functools

from pelican import signals, contents, generators, utils

__version__ = (0, 1, 1)

logger = logging.getLogger(__name__)


STATIC_EXTENSIONS = ('png', 'jpeg', 'jpg', 'gif', 'tif', 'tiff',
                     'doc', 'docx', 'xls',
                     'pdf',
                     'zip', 'tar', 'gz',
                     'js')


def ascii_tree(tree, prefix=[], last_prefix="", print_item=repr):
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

        for f in self.get_files(
                self.settings[kind + '_PATHS'],
                exclude=self.settings[kind + '_EXCLUDES'],
                extensions=extensions):
            utils.copy(os.path.join(self.path, f),
                       os.path.join(self.output_path, f))

# todo: Add the filenames of the assests to the url list in context
#       so that _update_content can fix relative URLs
# look for dirs and extract XXX_ in front for ordering
# overwrite with Title if a page exists

# If there is dir in PAGE_DIR, then create an output dir
# and add an index.hmtl (unless there is an index.md)

# Todo: Submit a PR to Pelican to allow cleanly replaceing PagesGenerator.
#       This is currently not possible, because in `__init__.py` in the method
#       `run` there is only a local variable `generators` that is not
#       available to any signal.


class HiPage(contents.Page):

    """
    HiPage inherits from `Page` and implements a hierarchical organization.

    There are the properties `parent` and `level` to access the hierarchy.
    A HiPage page re-uses the page template.

    A HiPage is iterable to go over all (direct) sub pages. It also supports
    the `__contains__` method based on the slug, so that `if "foobar" in page`
    works by checking if a page with slug "foobar" is among the sub_pages of
    this page.
    Under the hood, the hierarchy is implemented as an OrderedDict
    in the property `sub_pages`, where the slugs are the keys to the mapping.
    If you need to add sub pages, you'll have to work directly with the
    `sub_pages` OrderedDict.
    """

    def __init__(self, content, metadata=None, settings=None,
                 source_path=None, context=None, slug=None, title=None,
                 parent=None, **kws):
        self.parent = parent
        title = title or slug  # fall back to use slug for title

        if source_path is None:
            assert slug is not None,\
                "If no `source_path` given, a slug is needed."
            assert title is not None,\
                "If no `source_path` given, a title is needed."

        super(HiPage, self).__init__(content,
                                     metadata=metadata,
                                     settings=settings,
                                     source_path=source_path,
                                     context=context,
                                     **kws)
        # Only set slug/title if they were explicitly provided as keyword args,
        # otherwise let the `Page` constructor do its work.
        if slug is not None:
            self.slug = slug
        if title is not None:
            self.title = title
        self.sub_pages = OrderedDict()

    def __iter__(self):
        # The "iter" around is necessary because Jinja cannot yet handle
        # a ValuesView :-/
        return iter(self.sub_pages.values())

    def __contains__(self, item):
        if isinstance(item, contents.Page):
            item = item.slug
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
        bc = [(self.url, self.title)]
        for p in self.hierarchy:
            bc.append((p.url, p.title))
        return reversed(bc)

    def get_url_setting(self, key, separator="/"):
        """
        Helper building the path used for the properties `url` and `save_as`.

        `key` is either "usr" or "save_as".

        The get_url_setting method of Page usually returns something like
        "pages/spam.html" as it is defined by Pelican and can be configured
        by setting PAGE_LANG_URL etc.. We split this at the `separator`, so
        we can insert our hierachical layout, e.g.
        "pages/projects/fun/spam.thml"
        """
        # The root HiPage is not wanted here, and we ignore it by checking if
        # it has a parent.
        url = []
        slugs = reversed(list(p.slug for p in self.hierarchy if p.parent))
        orig = contents.Page.get_url_setting(self, key).split(separator)
        url.extend(orig[:-1])
        url.extend(slugs)
        url.extend(orig[-1:])
        return separator.join(url)

    # We have to override these properties, so that we can inject
    # our hierarchical layout.
    url = property(functools.partial(get_url_setting, key='url'))
    save_as = property(functools.partial(get_url_setting, key='save_as',
                                         separator=os.sep))

    # Override this method to avoid having the user to tell to use HIPAGE_...
    # settings instead of the default PAGE_... settings.
    def _expand_settings(self, key):
        """Expant to full qualified settings, but prefixed with "PAGE_"."""
        fq_key = ('%s_%s' % ("Page", key)).upper()
        return self.settings[fq_key].format(**self.url_format)

    def __hash__(self):
        """Ignoring the self.sub_pages and just make HiPage hashable."""
        return object.__hash__(self)

    def __repr__(self):
        return "<{cl} {url}>".format(cl=self.__class__.__name__, url=self.url)

    def print_tree(self):
        print(ascii_tree(self, print_item=lambda x: x.slug))


class HiPagesGenerator(generators.PagesGenerator):

    """
    Generate hierarchically arranged pages (of class `HiPage`).

    This class can replace `generator.PagesGenerator`.
    """

    def __init__(self, *args, **kws):
        super(HiPagesGenerator, self).__init__(*args, **kws)

    def generate_context(self):
        """
        Overwrites `PagesGenerator.generate_context` and builds up `HiPage`es.
        """
        root = HiPage("", slug='../index', title='Home', parent=None)
        all_pages = []
        hidden_pages = []

        path = os.path.join(self.path, self.settings['PAGE_PATHS'][0])
        all_pages, hidden_pages = self._scan_dir_r(
            path,
            exclude=self.settings['PAGE_EXCLUDES'],
            parent=root)

        self.pages, self.translations = utils.process_translations(all_pages)
        self.hidden_pages, self.hidden_translations = (
            utils.process_translations(hidden_pages))

        self._update_context(('pages', ))
        self.context['PAGES'] = self.pages
        self.context['PAGES_TREE'] = root
        logger.info(ascii_tree(root, print_item=lambda x: x.slug))

        signals.page_generator_finalized.send(self)

    def _scan_dir_r(self, path, exclude=None, parent=None, extensions=None):
        """
        Recursively scan `path` for source files to convert to `HiPages`.

        Symlinks are followed.

        `path`: Absolute directory path (`str`) to scan through.
        `exclude`: Directory names to exclude.
        `parent`: The `HiPage` that is used as the parent for items in `path`.
        """
        pages = []
        hidden_pages = []
        page_dir = os.path.join(self.path, self.settings['PAGE_PATHS'][0]) #XXX the [0] part is a hack!

        for item in sorted(os.listdir(path)):
            # Get the path to the `item` relative to the "PAGE_PATHS[0]" which
            # is "pages" in the default settings.
            rel_path = os.path.join(os.path.relpath(path, page_dir), item)

            if os.path.isfile(os.path.join(path, item)):
                # Using the include logic from parent class:
                if not self._include_path(rel_path, extensions):
                    logger.debug("Skipping {}".format(rel_path))
                    continue

                try:
                    page = self.readers.read_file(
                        base_path=page_dir,
                        path=rel_path,
                        content_class=HiPage,
                        context=self.context,
                        preread_signal=signals.page_generator_preread,
                        preread_sender=self,
                        context_signal=signals.page_generator_context,
                        context_sender=self)
                except Exception as e:
                    logger.warning('Could not process {}\n{}'
                                   .format(rel_path, e))
                    continue

                if not contents.is_valid_content(page, rel_path):
                    continue

                self.add_source_path(page)

                # XXX
                if page.slug in parent.sub_pages.keys():
                    # Instead of the virtual page use the parents's one
                    print("replace a virtual HiPage by this " + repr(page))
                    for sub in parent.sub_pages[page.slug]:
                        page.sub_pages[sub.slug] = sub
                    pages.remove(parent.sub_pages[page.slug])
                    del parent.sub_pages[page.slug]
                    print("so now parent.sub_pages is " + repr(parent.sub_pages))

                if page.status == "published":
                    pages.append(page)
                    page.parent = parent
                    if page.in_default_lang:
                        # Always adding the page if it is in the default lang,
                        # possibly overwriting an older assignment from a
                        # translated page that happend to be processed before:
                        parent.sub_pages[page.slug] = page
                    elif page.slug not in parent:
                        # Only add a translation to the parent, if there is
                        # not already a page with the same slug in parent:
                        parent.sub_pages[page.slug] = page
                    else:
                        logger.debug(parent.slug + " has already another "
                                     "entry for " + page.slug)

                elif page.status == "hidden":
                    # Don't add hidden pages to the parent. They are still
                    # there but not in the `sub_pages` dict of parent.
                    hidden_pages.append(page)
                else:
                    logger.warning("Unknown status '%s' for file %s, "
                                   "skipping it." %
                                   (repr(page.status), repr(rel_path)))

            elif os.path.isdir(os.path.join(path, item)):

                if item in exclude:
                    continue

                # Virtual page, that is used when there is not already a page
                # with the same slug under the current `parent`.
                page = HiPage("", source_path=os.path.join(page_dir, rel_path),
                              slug=utils.slugify(item),
                              parent=parent)

                # Because we allow to override the HiPage for a directory
                # `foo` by providing a `foo.md` file, we check now whether the
                # file already exists, or an empty `HiPage` should be created
                # for this directory.
                print(page.slug)
                if page.slug in parent.sub_pages.keys():
                    # Instead of the virtual page use the parents's one
                    print("don't use virtual page... " + repr(parent.sub_pages))
                    page = parent.sub_pages[page.slug]
                else:
                    # Add the virtual page (created above) to the parent
                    print("adding virt. page: " + page.slug)
                    parent.sub_pages[page.slug] = page

                # Recursively descent into the directory
                p, h = self._scan_dir_r(path=os.path.join(page_dir, rel_path),
                                        exclude=exclude,
                                        parent=page)
                self.add_source_path(page)
                pages.append(page)
                pages.extend(p)
                hidden_pages.extend(h)

            else:
                raise Exception("not a dir and not a file")  # possible at all?

        return pages, hidden_pages


def remove_normal_pages(self):
    """This is a hack to keep Pelican from generating the normal Pages."""
    if self.__class__ == generators.PagesGenerator:
        def noop(self, *args, **kws):
            logger.debug(self.__class__.__name__ +
                         ": hierarchy plugin: Dummy `noop` called instead of "
                         "`get_files` to replace `Page` by `HiPage`.")
            return []
        # The easiest way, I found, was just to make `get_files` a noop.
        self.get_files = noop
        logger.warn("hierarchy plugin: `get_files()` of "
                    + self.__class__.__name__ +
                    " disabled in favor of `HiPagesGenerator`.")


def add_hi_pages_generator(self):
    return HiPagesGenerator


def add_copy_statics_generator(self):
    return CopyStaticAssetsGenerator


# A pelican plugin has to have this function. It's the entry point.
def register():
    signals.get_generators.connect(add_hi_pages_generator)
    signals.get_generators.connect(add_copy_statics_generator)
    signals.page_generator_init.connect(remove_normal_pages)
