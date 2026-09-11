/* Unseated Series launch settings. Shared by /series, /season1, and the
   homepage premiere line, so the date is set in one place.

   premiereDate   e.g. 'September 18'. Blank shows "Next Week" everywhere.
   trailerUrl     YouTube watch, youtu.be, or embed URL. Blank keeps the
                  poster on /season1 with "Trailer Coming Soon".
   episodeOneUrl  Full episode URL. When set, /season1 shows "Watch Episode
                  One" and the status reads "Now Streaming".
   youtubeUrl     Channel URL. Shows the "Subscribe on YouTube" button.
   notifyUrl      Where "Get Notified" goes. Blank falls back to /community. */
window.SEASON_ONE = {
  premiereDate:  '',
  trailerUrl:    '',
  episodeOneUrl: '',
  youtubeUrl:    '',
  notifyUrl:     ''
};
