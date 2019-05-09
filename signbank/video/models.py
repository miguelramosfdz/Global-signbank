""" Models for the video application
keep track of uploaded videos and converted versions
"""

from django.db import models
from django.conf import settings
import sys, os, time, shutil

from signbank.video.convertvideo import extract_frame, convert_video, ffmpeg

from django.core.files.storage import FileSystemStorage
from django.contrib.auth import models as authmodels
from signbank.settings.base import WRITABLE_FOLDER, GLOSS_VIDEO_DIRECTORY, GLOSS_IMAGE_DIRECTORY, FFMPEG_PROGRAM
# from django.contrib.auth.models import User
from datetime import datetime

from signbank.dictionary.models import *

if sys.argv[0] == 'mod_wsgi':
    from signbank.dictionary.models import *
else:
    from signbank.dictionary.models import Gloss


class Video(models.Model):
    """A video file stored on the site"""

    # video file name relative to MEDIA_ROOT
    videofile = models.FileField("Video file in h264 mp4 format", upload_to=settings.VIDEO_UPLOAD_LOCATION)

    def __str__(self):
        return self.videofile.name

    def process(self):
        """The clean method will try to validate the video
        file format, optimise for streaming and generate
        the poster image"""

        self.poster_path()
        # self.ensure_mp4()


    def poster_path(self, create=True):
        """Return the path of the poster image for this
        video, if create=True, create the image if needed
        Return None if create=False and the file doesn't exist"""

        vidpath, ext = os.path.splitext(self.videofile.path)
        poster_path = vidpath + ".jpg"

        if not os.path.exists(poster_path):
            if create:
                # need to create the image
                extract_frame(self.videofile.path, poster_path)
            else:
                return None

        return poster_path


    def poster_url(self):
        """Return the URL of the poster image for this video"""

        # generate the poster image if needed
        path = self.poster_path()

        # splitext works on urls too!
        vidurl, ext = os.path.splitext(self.videofile.url)
        poster_url = vidurl + ".jpg"

        return poster_url


    def get_absolute_url(self):
        return self.videofile.url


    def ensure_mp4(self):
        """Ensure that the video file is an h264 format
        video, convert it if necessary"""

        # convert video to use the right size and iphone/net friendly bitrate
        # create a temporary copy in the new format
        # then move it into place

        # print "ENSURE: ", self.videofile.path

        (basename, ext) = os.path.splitext(self.videofile.path)
        tmploc = basename + "-conv.mp4"
        err = convert_video(self.videofile.path, tmploc, force=True)
        # print tmploc
        shutil.move(tmploc, self.videofile.path)


    def delete_files(self):
        """Delete the files associated with this object"""

        try:
            os.unlink(self.videofile.path)
            poster_path = self.poster_path(create=False)
            if poster_path:
                os.unlink(poster_path)
        except:
            pass


import shutil

class GlossVideoStorage(FileSystemStorage):
    """Implement our shadowing video storage system"""

    def __init__(self, location=settings.MEDIA_ROOT, base_url=settings.MEDIA_URL):
        super(GlossVideoStorage, self).__init__(location, base_url)


    # def get_valid_name(self, name):
    #     """Generate a valid name, we use directories named for the
    #     first two digits in the filename to partition the videos"""
    #
    #     (targetdir, basename) = os.path.split(name)
    #
    #     path = os.path.join(str(basename)[:2], str(basename))
    #
    #     result = os.path.join(targetdir, path)
    #
    #     return result


storage = GlossVideoStorage()

# The 'action' choices are used in the GlossVideoHistory class
ACTION_CHOICES = (('delete', 'delete'),
                  ('upload', 'upload'),
                  ('rename', 'rename'),
                  ('watch', 'watch'),
                  )


class GlossVideoHistory(models.Model):
    """History of video uploading and deletion"""

    action = models.CharField("Video History Action",max_length=6, choices=ACTION_CHOICES, default='watch')
    # When was this action done?
    datestamp = models.DateTimeField("Date and time of action", auto_now_add=True)  # WAS: default=datetime.now()
    # See 'vfile' in video.views.addvideo
    uploadfile = models.TextField("User upload path", default='(not specified)')
    # See 'goal_location' in addvideo
    goal_location = models.TextField("Full target path", default='(not specified)')

    # WAS: Many-to-many link: to the user that has uploaded or deleted this video
    # WAS: actor = models.ManyToManyField("", User)
    # The user that has uploaded or deleted this video
    actor = models.ForeignKey(authmodels.User)

    # One-to-many link: to the Gloss in dictionary.models.Gloss
    gloss = models.ForeignKey(Gloss)

    def __str__(self):

        # Basic feedback from one History item: gloss-action-date
        name = self.gloss.idgloss + ': ' + self.action + ', (' + str(self.datestamp) + ')'
        return name.encode('ascii', errors='replace')

    class Meta:
        ordering = ['datestamp']


def get_video_file_path(instance, filename, version=0):
    """
    Return the full path for storing an uploaded video
    :param instance: A GlossVideo instance
    :param filename: the original file name
    :param version: the version to determine the number of .bak extensions
    :return: 
    """

    idgloss = instance.gloss.idgloss

    def get_two_letter_dir():
        foldername = idgloss[:2]

        if len(foldername) == 1:
            foldername += '-'

        return foldername

    video_dir = settings.GLOSS_VIDEO_DIRECTORY
    dataset_dir = instance.gloss.lemma.dataset.acronym
    two_letter_dir = get_two_letter_dir()
    filename = idgloss + '-' + str(instance.gloss.id) + '.mp4' + (version * ".bak")

    path = os.path.join(video_dir, dataset_dir, two_letter_dir, filename)
    return path


def get_path_with_small(path):
    path_no_extension, extension = os.path.splitext(path)
    if not path_no_extension.endswith('_small'):
        return path_no_extension + '_small' + extension
    else:
        return path


class GlossVideo(models.Model):
    """A video that represents a particular idgloss"""

    videofile = models.FileField("video file", upload_to=get_video_file_path, storage=storage)

    gloss = models.ForeignKey(Gloss)

    ## video version, version = 0 is always the one that will be displayed
    # we will increment the version (via reversion) if a new video is added
    # for this gloss
    version = models.IntegerField("Version", default=0)

    def process(self):
        """The clean method will try to validate the video
        file format, optimise for streaming and generate
        the poster image"""

        self.poster_path()
        # self.ensure_mp4()

    def poster_path(self, create=True):
        """Return the path of the poster image for this
        video, if create=True, create the image if needed
        Return None if create=False and the file doesn't exist"""

        vidpath, ext = os.path.splitext(self.videofile.path)
        poster_path = vidpath + ".jpg"

        if not os.path.exists(poster_path):
            if create:
                # need to create the image
                extract_frame(self.videofile.path, poster_path)
            else:
                return None

        return poster_path

    def poster_url(self):
        """Return the URL of the poster image for this video"""

        # generate the poster image if needed
        path = self.poster_path()

        # splitext works on urls too!
        vidurl, ext = os.path.splitext(self.videofile.url)
        poster_url = vidurl + ".jpg"

        return poster_url

    def get_absolute_url(self):

        return self.videofile.url

    def ensure_mp4(self):
        """Ensure that the video file is an h264 format
        video, convert it if necessary"""

        # convert video to use the right size and iphone/net friendly bitrate
        # create a temporary copy in the new format
        # then move it into place

        # print "ENSURE: ", self.videofile.path

        (basename, ext) = os.path.splitext(self.videofile.path)
        tmploc = basename + "-conv.mp4"
        err = convert_video(self.videofile.path, tmploc, force=True)
        # print tmploc
        shutil.move(tmploc, self.videofile.path)

    def small_video(self):
        """Return the URL of the poster image for this video"""
        small_video_path = get_path_with_small(self.videofile.path)
        if os.path.exists(small_video_path):
            return small_video_path
        else:
            return None

    def make_small_video(self):
        from CNGT_scripts.python.resizeVideos import VideoResizer

        video_file_full_path = os.path.join(WRITABLE_FOLDER, str(self.videofile))
        try:
            resizer = VideoResizer([video_file_full_path], FFMPEG_PROGRAM, 180, 0, 0)
            resizer.run()
        except:
            print("Error resizing video: ", video_file_full_path)

    def make_poster_image(self):
        from signbank.tools import generate_still_image
        try:
            generate_still_image(self)
        except:
            import sys
            print('Error generating still image', sys.exc_info())

    def delete_files(self):
        """Delete the files associated with this object"""

        small_video_path = self.small_video()
        try:
            os.unlink(self.videofile.path)
            poster_path = self.poster_path(create=False)
            if small_video_path:
                os.unlink(small_video_path)
            if poster_path:
                os.unlink(poster_path)
        except:
            pass

    def get_mobile_url(self):
        """Return a URL to serve the mobile version of this
        video, this uses MEDIA_MOBILE_URL as a prefix
        rather than MEDIA_URL but is otherwise the same"""

        url = self.get_absolute_url()
        return url.replace(settings.MEDIA_URL, settings.MEDIA_MOBILE_URL)

    def reversion(self, revert=False):
        """We have a new version of this video so increase
        the version count here and rename the video
        to video.mp4.bak.V where V is the version number

        unless revert=True, in which case we go the other
        way and decrease the version number, if version=0
        we delete ourselves"""

        if revert:
            print("REVERT VIDEO", self.videofile.name, self.version)
            if self.version==0:
                print("DELETE VIDEO VIA REVERSION", self.videofile.name)
                self.delete_files()
                self.delete()
                return
            else:
                # remove .bak from filename and decrement the version
                (newname, bak) = os.path.splitext(self.videofile.name)
                if bak != '.bak':
                    # hmm, something bad happened
                    raise Exception('Unknown suffix on stored video file. Expected .bak')
                self.version -= 1
        else:
            # find a name for the backup, a filename that isn't used already
            newname = self.videofile.name
            while os.path.exists(os.path.join(storage.location, newname)):
                self.version += 1
                newname = newname + ".bak"

        # now do the renaming
        
        os.rename(os.path.join(storage.location, self.videofile.name), os.path.join(storage.location, newname))
        # also remove the post image if present, it will be regenerated
        poster = self.poster_path(create=False)
        if poster != None:
            os.unlink(poster)
        self.videofile.name = newname
        self.save()


    def __str__(self):
        # this coercion to a string type sometimes causes special characters in the filename to be a problem
        # code has been introduced elsewhere to make sure paths are the correct encoding
        return self.videofile.name

    def move_video(self, move_files_on_disk=True):
        """
        Calculates the new path, moves the video file to the new path and updates the videofile field
        :return: 
        """
        old_path = str(str(self.videofile))
        new_path = get_video_file_path(self, "", self.version)
        if old_path != new_path:
            if move_files_on_disk:
                source = os.path.join(settings.WRITABLE_FOLDER, old_path)
                destination = os.path.join(settings.WRITABLE_FOLDER, new_path)
                if os.path.exists(source):
                    destination_dir = os.path.dirname(destination)
                    if not os.path.exists(destination_dir):
                        os.makedirs(destination_dir)
                    if os.path.isdir(destination_dir):
                        shutil.move(source, destination)

                # Small video
                (source_no_extension, ext) = os.path.splitext(source)
                source_small = get_path_with_small(source)  #source_no_extension + '_small' + ext
                (destination_no_extension, ext) = os.path.splitext(destination)
                destination_small = get_path_with_small(destination)  #destination_no_extension + '_small' + ext
                print("source_small", source_small)
                if os.path.exists(source_small):
                    shutil.move(source_small, destination_small)

                # Image
                source_image = source_no_extension.replace(settings.GLOSS_VIDEO_DIRECTORY, settings.GLOSS_IMAGE_DIRECTORY)\
                               + '.png'
                destination_image = destination_no_extension.replace(settings.GLOSS_VIDEO_DIRECTORY, settings.GLOSS_IMAGE_DIRECTORY)\
                               + '.png'
                if os.path.exists(source_image):
                    destination_image_dir = os.path.dirname(destination_image)
                    if not os.path.exists(destination_image_dir):
                        os.makedirs(destination_image_dir)
                    if os.path.isdir(destination_image_dir):
                        shutil.move(source_image, destination_image)

            self.videofile.name = new_path
            self.save()


@receiver(models.signals.post_save, sender=Dataset)
def process_dataset_changes(sender, instance, **kwargs):
    """
    Makes changes to GlossVideos if a Dataset has been changed.
    :param sender: 
    :param instance: 
    :param kwargs: 
    :return: 
    """
    # If the acronym has been changed, change all GlossVideos
    # and rename directories.
    dataset = instance
    if dataset.acronym != dataset._initial['acronym']:
        # Move all media
        glossvideos = GlossVideo.objects.filter(gloss__lemma__dataset=dataset)
        for glossvideo in glossvideos:
            glossvideo.move_video(move_files_on_disk=False)

        # Rename dirs
        glossvideo_path_original = os.path.join(WRITABLE_FOLDER, GLOSS_VIDEO_DIRECTORY, dataset._initial['acronym'])
        glossvideo_path_new = os.path.join(WRITABLE_FOLDER, GLOSS_VIDEO_DIRECTORY, dataset.acronym)
        os.rename(glossvideo_path_original, glossvideo_path_new)

        glossimage_path_original = os.path.join(WRITABLE_FOLDER, GLOSS_IMAGE_DIRECTORY, dataset._initial['acronym'])
        glossimage_path_new = os.path.join(WRITABLE_FOLDER, GLOSS_IMAGE_DIRECTORY, dataset.acronym)
        os.rename(glossimage_path_original, glossimage_path_new)

    # If the default language has been changed, change all GlossVideos
    # and move all video/poster files accordingly.
    if dataset.default_language != dataset._initial['default_language']:
        # Move all media
        glossvideos = GlossVideo.objects.filter(gloss__lemma__dataset=dataset)
        for glossvideo in glossvideos:
            glossvideo.move_video(move_files_on_disk=True)


@receiver(models.signals.post_save, sender=LemmaIdglossTranslation)
def process_lemmaidglosstranslation_changes(sender, instance, **kwargs):
    """
    Makes changes to GlossVideos if a LemmaIdglossTranslation has been changed.
    :param sender: 
    :param instance: 
    :param kwargs: 
    :return: 
    """
    lemmaidglosstranslation = instance
    print("LemmaIdglossTranslation", lemmaidglosstranslation)
    glossvideos = GlossVideo.objects.filter(gloss__lemma__lemmaidglosstranslation=lemmaidglosstranslation)
    for glossvideo in glossvideos:
        glossvideo.move_video(move_files_on_disk=True)
