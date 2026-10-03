# Reading a record image

What a reader of a record image writes, one person at a time, through the person
screen's transcription path (`app/person/server.py` `transcribe`, the form on a held
record). A model reads an image by this text; the form is how a person writes the same
things. The sha256 of this file as it stands when a reading is made is the reading's
prompt hash on its extractor row, so a changed text is a new reader row.

Write each person the record names as one persona:

- **Name and role.** The name as the record writes it, mistakes included: an error in a
  record is never corrected here, it becomes an alias later. The role in the record's own
  word (head, wife, son, boarder, groom, bride, deceased, informant, named on the stone).
  `sex` only when the record states it or the role does.
- **Facts as written.** What the record states of the person, in the record's words and
  the form's fields: `age`, `birth_date`, `birth_place`, `death_date`, `death_place`,
  `residence`, `marriage_date`, `marriage_place`, `occupation`, `marital_status`; any
  other thing the record writes about the person goes in `as_written` under the label the
  record gives it. Nothing from outside the image.
- **A birth worked out from an age.** When the record gives an age and not a birth, give
  the `age` and the record's `year` and leave `birth_date` empty: the path writes the
  birth as calculated from them (qualifier `calculated`, so the matcher allows two
  years). A date the record itself states goes in `birth_date`, never marked calculated.
- **The record's own number.** `number`, on the persona the record is about, when the
  record gives itself one (a certificate's state file number, a register's entry number),
  as written: it is what tells another copy of the same record (a state index's line) it
  is this one.
- **The relation to the head.** The relationship the record states, in its own words,
  from this person toward a persona already written on the same record
  (`relations`: the `persona_id`, the `kind`, the words as `text`). Write the head first.
- **Where on the image.** Every persona carries the `line` it stands on (counted from the
  top of the page, the first line being 1) or the `bbox` of its row on the image
  (`[x, y, width, height]` in the image's own pixels, with `page` when the image holds
  more than one). A person whose place on the image cannot be given is not read.
- **What the image is.** `image_is`, once for the record: `record` when the image is the
  record made at the event (a register page, a certificate, a census schedule, a
  gravestone), or `index` when it is an index, an abstract or a transcript of one. An
  index page whose own name is a slip (an indexer's transposition or misreading) is
  written as the page spells it, and read the same way.

A reading names its reader: `llm:<model id>` for a model, `user:<name>` for a person.
