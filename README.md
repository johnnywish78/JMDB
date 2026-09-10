# JMDB
============================================================
JMDB — JOHNNY'S MEDIA DATABASE
MASTER BUILD SPECIFICATION
ZERO → 100%
VERSION 1.0.0
============================================================

ROLE
============================================================

You are the lead architect, senior desktop application
developer, UI/UX designer, media-engine developer, browser
engine developer, database engineer, security engineer and
QA engineer responsible for completing JMDB from zero to a
production-ready v1.0.0 desktop application.

Product name:

JMDB

Full name:

Johnny's Media Database

This specification is the complete source of truth.

Do not treat JMDB as a prototype.

Do not build a mockup.

Do not build a static dashboard.

Do not create fake controls.

Do not create fake statistics.

Do not create fake playback.

Do not create fake browser functionality.

Every required feature must be genuinely implemented,
connected, persistent and testable.

============================================================
1. PRODUCT PURPOSE
============================================================

JMDB is a professional personal desktop media environment.

It combines:

• Personal media library
• Movie management
• TV Show management
• Episode management
• Music management
• People database
• Metadata
• Artwork
• Playback
• Playback history
• Resume
• Favorites
• Watchlist
• Collections
• Recommendations
• Statistics
• Online services
• Full embedded Chromium Browser
• Download manager
• Application settings

The final product must feel like one unified application.

It must combine the functionality of:

premium cinematic media center
+
professional media database
+
modern desktop browser
+
personal media player

It must NOT look like a generic CRUD/admin application.

============================================================
2. PRIMARY DESIGN PRINCIPLES
============================================================

Priority order:

1. Functionality
2. Reliability
3. Data integrity
4. Cross-platform compatibility
5. Security
6. Usability
7. Visual quality
8. Performance

Never sacrifice functionality merely to make a screenshot
look impressive.

Never hide an incomplete feature behind a beautiful UI.

If something cannot be supported identically on both target
operating systems, implement the best native solution for
each platform and document the platform-specific behavior.

Never fake successful behavior.

============================================================
3. OFFICIAL TARGET PLATFORMS
============================================================

JMDB has TWO official desktop targets:

PRIMARY TARGETS:

• Linux Desktop
• Windows Desktop

Both platforms are first-class targets.

Linux is NOT merely a development platform.

Windows is NOT an optional future platform.

The architecture, filesystem handling, process management,
browser behavior, player integration, settings, packaging
and installation process must account for BOTH platforms.

Supported architecture should remain portable to macOS where
practical, but macOS is NOT required for v1.0.0 acceptance.

------------------------------------------------------------
LINUX
------------------------------------------------------------

Target:

Modern 64-bit Linux desktop.

The implementation must work with standard Linux filesystem
paths, permissions, processes and desktop behavior.

Support:

• Linux user data directories
• Linux executable discovery
• Linux process management
• Linux filesystem permissions
• Linux external browser detection
• Linux MPV/VLC detection
• Linux packaging

Preferred Linux package:

AppImage

A native development/unpacked build must also work.

------------------------------------------------------------
WINDOWS
------------------------------------------------------------

Target:

Modern 64-bit Windows desktop.

The implementation must properly support:

• Windows filesystem paths
• Windows drive letters
• Windows permissions
• Windows executable discovery
• Windows process management
• Windows external browser detection
• Windows MPV/VLC detection
• Windows user data directories
• Windows downloads directory
• Windows application startup
• Windows packaging

Preferred Windows package:

NSIS installer and/or portable build.

Do not assume Linux paths when running on Windows.

Do not use shell commands that only work on Linux.

Do not hard-code:

/
~/
 /home/
 /usr/
 /bin/

for application logic.

Use platform-aware path APIs.

============================================================
4. CROSS-PLATFORM RULE
============================================================

All application code must distinguish between:

• platform-independent application logic
• Linux-specific implementation
• Windows-specific implementation

Use appropriate platform APIs and abstractions.

Examples of areas requiring platform abstraction:

• filesystem paths
• application data paths
• executable discovery
• process spawning
• external browser launching
• MPV executable discovery
• VLC executable discovery
• default download directory
• temporary directories
• application startup
• packaging
• file manager integration

Never solve a Windows requirement by assuming Linux behavior.

Never solve a Linux requirement by assuming Windows behavior.

============================================================
5. APPLICATION ARCHITECTURE
============================================================

Use a layered architecture.

High-level architecture:

Electron
    |
    +-- Main Process
    |
    +-- Secure Preload
    |
    +-- Renderer UI
    |
    +-- Browser subsystem
    |
    +-- Player subsystem
    |
    +-- Download subsystem
    |
    |
    +------ IPC ------+
                     |
                 Application
                   Backend
                     |
              Service Layer
                     |
              Repository Layer
                     |
                  SQLite
                     |
                Local Files

The renderer must never receive unrestricted Node.js access.

Use:

contextIsolation = true

nodeIntegration = false

Secure preload bridge.

Validate IPC messages.

Do not expose arbitrary filesystem operations.

Do not expose arbitrary shell execution.

Do not expose API keys to web pages.

============================================================
6. COMPLETE PROJECT STRUCTURE
============================================================

Create the project with this logical structure:

JMDB/
│
├── electron/
│   │
│   ├── main.js
│   │
│   ├── main/
│   │   ├── app-lifecycle.js
│   │   ├── window-manager.js
│   │   ├── ipc.js
│   │   │
│   │   ├── browser/
│   │   │   ├── browser-manager.js
│   │   │   ├── tab-manager.js
│   │   │   ├── session-manager.js
│   │   │   ├── navigation.js
│   │   │   ├── permissions.js
│   │   │   ├── context-menu.js
│   │   │   ├── cookies.js
│   │   │   ├── history.js
│   │   │   ├── privacy.js
│   │   │   ├── external-browser.js
│   │   │   └── browser-settings.js
│   │   │
│   │   ├── downloads/
│   │   │   ├── download-manager.js
│   │   │   ├── download-item.js
│   │   │   └── download-store.js
│   │   │
│   │   ├── player/
│   │   │   ├── player-manager.js
│   │   │   ├── mpv-manager.js
│   │   │   ├── playback-ipc.js
│   │   │   ├── playback-state.js
│   │   │   ├── tracks.js
│   │   │   ├── subtitles.js
│   │   │   └── autoplay.js
│   │   │
│   │   └── services/
│   │       ├── youtube.js
│   │       ├── telegram.js
│   │       ├── spotify.js
│   │       └── tv-time.js
│   │
│   ├── preload/
│   │   └── preload.js
│   │
│   ├── renderer/
│   │   │
│   │   ├── index.html
│   │   │
│   │   ├── assets/
│   │   │   ├── icons/
│   │   │   ├── logos/
│   │   │   ├── artwork/
│   │   │   └── fonts/
│   │   │
│   │   ├── components/
│   │   │   ├── sidebar/
│   │   │   ├── topbar/
│   │   │   ├── cards/
│   │   │   ├── modals/
│   │   │   ├── dialogs/
│   │   │   ├── buttons/
│   │   │   ├── forms/
│   │   │   ├── empty-states/
│   │   │   ├── error-states/
│   │   │   └── notifications/
│   │   │
│   │   ├── pages/
│   │   │   ├── home/
│   │   │   ├── movies/
│   │   │   ├── movie-detail/
│   │   │   ├── tv/
│   │   │   ├── tv-detail/
│   │   │   ├── music/
│   │   │   ├── album-detail/
│   │   │   ├── artist-detail/
│   │   │   ├── people/
│   │   │   ├── person-detail/
│   │   │   ├── recommended/
│   │   │   ├── favorites/
│   │   │   ├── watchlist/
│   │   │   ├── history/
│   │   │   ├── collections/
│   │   │   ├── services/
│   │   │   ├── browser/
│   │   │   ├── statistics/
│   │   │   └── settings/
│   │   │
│   │   ├── browser/
│   │   │   ├── tabs/
│   │   │   ├── toolbar/
│   │   │   ├── permissions/
│   │   │   ├── downloads/
│   │   │   └── settings/
│   │   │
│   │   ├── player/
│   │   │   ├── player-ui.js
│   │   │   ├── controls.js
│   │   │   ├── timeline.js
│   │   │   ├── tracks.js
│   │   │   ├── subtitles.js
│   │   │   └── queue.js
│   │   │
│   │   ├── state/
│   │   ├── services/
│   │   ├── api/
│   │   ├── utils/
│   │   └── styles/
│   │       ├── tokens.css
│   │       ├── themes.css
│   │       ├── layout.css
│   │       ├── components.css
│   │       ├── cards.css
│   │       ├── browser.css
│   │       └── player.css
│   │
│   └── tests/
│       ├── browser/
│       ├── downloads/
│       ├── player/
│       ├── ipc/
│       ├── services/
│       └── ui/
│
├── backend/
│   │
│   ├── app.py
│   │
│   ├── api/
│   │   ├── health.py
│   │   ├── media.py
│   │   ├── movies.py
│   │   ├── tv.py
│   │   ├── music.py
│   │   ├── people.py
│   │   ├── playback.py
│   │   ├── favorites.py
│   │   ├── watchlist.py
│   │   ├── collections.py
│   │   ├── history.py
│   │   ├── recommendations.py
│   │   ├── statistics.py
│   │   ├── scanner.py
│   │   ├── metadata.py
│   │   └── settings.py
│   │
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   ├── security.py
│   │   └── paths.py
│   │
│   ├── database/
│   │   ├── database.py
│   │   ├── migrations/
│   │   └── schema.py
│   │
│   ├── models/
│   ├── repositories/
│   └── services/
│
├── data/
├── config/
├── scripts/
├── tests/
├── docs/
│
├── .env.example
├── package.json
├── pyproject.toml
├── requirements.txt
├── electron-builder.yml
├── run.py
└── README.md

Do not create empty directories merely to make the project
look complete.

Every created file must have a real purpose.

============================================================
7. REQUIRED NODE / ELECTRON STACK
============================================================

Use a current stable Electron version compatible with the
supported Linux and Windows targets.

Required:

electron
electron-builder

Only add additional Node packages when technically justified.

Do not introduce unnecessary dependencies.

If a frontend framework is used, use one consistent stack.

Do not mix multiple frontend frameworks.

============================================================
8. REQUIRED PYTHON STACK
============================================================

Minimum:

Python 3.14+

FastAPI
Uvicorn
Pydantic
SQLAlchemy
Alembic
httpx
pytest
pytest-asyncio

Media:

python-mpv
python-vlc

Additional libraries may be used when genuinely required.

Possible media/file metadata libraries:

mutagen
pymediainfo

Every dependency must have a concrete purpose.

============================================================
9. SYSTEM DEPENDENCIES
============================================================

Detect system dependencies separately on Linux and Windows.

Potential components:

MPV
VLC
FFmpeg where required
Electron/Chromium runtime dependencies

Diagnostics must report:

• executable availability
• executable path
• version
• permissions
• compatibility
• platform

Never report a dependency as available when it is not.

============================================================
10. DATABASE
============================================================

Use SQLite as the primary local database.

Use migrations.

Never modify production schema without a migration.

Required logical entities:

media
movies
tv_shows
seasons
episodes
artists
albums
tracks
people
credits
genres
media_genres
files
library_locations
artwork
playback_state
playback_sessions
favorites
watchlist
collections
collection_items
recommendations
services
settings
browser_history
browser_downloads

Each entity must have:

• primary key
• appropriate foreign keys
• indexes
• timestamps where appropriate
• uniqueness constraints where appropriate

Media files must be linked to media records.

Do not duplicate the same media item merely because it exists
in multiple scanned locations.

============================================================
11. DATABASE INTEGRITY
============================================================

Scanner must be idempotent.

Repeated scans must not create duplicates.

Deleted files must be detectable.

Missing files must be represented safely.

Metadata refresh must update existing records.

Artwork cache must not create unnecessary duplicates.

All critical operations must be transactional.

============================================================
12. APPLICATION DATA PATHS
============================================================

Use platform-appropriate application-data directories.

Linux and Windows MUST have separate path handling.

Do not assume that the source directory is the permanent
runtime data directory.

Store separately:

database
artwork
cache
downloads
browser profile
logs

Development mode may optionally use project-local data.

Production mode must use proper user application-data
locations.

Allow a configurable data directory where appropriate.

============================================================
13. API KEYS / SECRETS
============================================================

Support configuration for:

TMDB
OMDb
Fanart.tv
Last.fm

Never hard-code secrets.

Never put secrets into renderer JavaScript.

Never expose API keys to Browser Hub pages.

Use environment variables and/or secure platform storage.

Support platform-appropriate secure storage where practical.

Settings UI must display:

Configured
Not Configured
Invalid

Never display complete secret values.

============================================================
14. METADATA PROVIDERS
============================================================

Movies/TV:

TMDB
OMDb
TVmaze
iTunes

Music:

MusicBrainz
TheAudioDB
Last.fm

IMDb:

Use IDs, deep links and cross references where technically
and legally appropriate.

Do not scrape IMDb unless explicitly permitted and technically
appropriate.

EMDB:

Do not invent an EMDB API.

If no supported public API exists, do not create fake
integration.

TV Time:

Treat TV Time as an online service accessed through the
Browser Hub.

Do not invent a TV Time API.

============================================================
15. METADATA PIPELINE
============================================================

The metadata pipeline must operate as:

local discovery
→ media identification
→ provider search
→ best-match resolution
→ provider IDs
→ metadata persistence
→ artwork acquisition
→ cast/crew
→ final library update

Metadata refresh must be asynchronous.

The UI must remain responsive.

Provider failures must not destroy existing metadata.

Use fallback providers where configured and appropriate.

============================================================
16. ARTWORK SYSTEM
============================================================

Support:

poster
backdrop
logo where available
cast image
crew image
artist image
album artwork

Artwork must be cached locally.

Use deterministic or content-addressed storage.

Avoid repeated downloads.

Handle failed artwork gracefully.

============================================================
17. LIBRARY SCANNER
============================================================

Library Locations page.

Actions:

Add Location
Browse
Remove
Scan
Scan Everything

Scanner must detect:

Movies
TV Shows
Episodes
Music

Support common media formats.

Use metadata and filename/path analysis to identify media.

When identification is uncertain:

do not invent metadata.

Represent the item as unresolved or requiring matching.

============================================================
18. SCAN PROGRESS
============================================================

Display real:

files scanned
files discovered
current file
percentage
status
errors
last scan
elapsed time
ETA where possible

Progress must represent actual scanner state.

Never use fake timers.

Allow safe cancellation.

Interrupted scans must not corrupt the database.

============================================================
19. MOVIE IDENTIFICATION
============================================================

Implement robust identification using:

• filename analysis
• directory structure
• embedded metadata where available
• provider matching
• year information where available
• user correction where necessary

Do not hard-code specific media titles.

Do not include sample titles in production code.

============================================================
20. TV IDENTIFICATION
============================================================

Implement robust detection of:

• shows
• seasons
• episodes

Support common episode numbering conventions and directory
structures.

Do not hard-code specific show names.

Do not include sample shows in production code.

============================================================
21. MUSIC IDENTIFICATION
============================================================

Read embedded metadata where available.

Support:

artist
album
track
track number
disc number
year
genre

Use configured music metadata services for enrichment.

Do not hard-code sample artists or albums.

============================================================
22. GLOBAL UI
============================================================

Permanent desktop shell:

Sidebar
Top Bar
Scrollable Content

Sidebar must remain usable.

Content must scroll independently.

Browser and player must use the available application area
correctly.

============================================================
23. BRANDING
============================================================

Display:

JMDB

Johnny's Media Database

Version 1.0.0

Create a dedicated JMDB visual identity.

Logo concept:

minimal
cinematic
professional
media-related
clean geometry
subtle crimson accent

Do not use emoji as the logo.

============================================================
24. SIDEBAR NAVIGATION
============================================================

Exact order:

1. Home
2. Movies
3. TV Shows
4. Music
5. People
6. Recommended
7. Favorites
8. Watchlist
9. History
10. Collections
11. Services
12. Browser Hub
13. Statistics
14. Settings

Use one consistent icon family.

No emoji.

============================================================
25. TOP BAR
============================================================

Global search:

Search movies, shows, people, music… (Ctrl+K)

Controls:

Scan Library
Theme Toggle
Notifications/status

Ctrl+K focuses global search.

============================================================
26. THEMES
============================================================

Support:

Dark
Light
System

Theme must:

• apply immediately
• persist after restart
• affect all application surfaces
• remain consistent across browser shell and player UI

Dark:

near-black
charcoal
graphite cards
near-white text
muted gray secondary text
cinematic crimson accent

Light:

warm neutral background
white cards
dark text
same accent

Avoid excessive gradients.

Avoid excessive glow.

============================================================
27. HOME
============================================================

Hero:

real artwork
backdrop
title
year
runtime
genres
rating
overview

Actions:

Play
More Info
Favorite
Watchlist

Rows:

Continue Watching
Recently Added
New Episodes
Favorites
Recommended
Library Statistics

All information must come from real application data.

No hard-coded sample content.

============================================================
28. MOVIES
============================================================

Provide:

Search
Sort
Filter
Grid/List

Sort:

Title
Year
Rating
Recently Added

Filters:

Genre
Unwatched
Favorites
Watchlist

Cards display real database information.

Hover actions:

Play
Details
Favorite
Watchlist

============================================================
29. MOVIE DETAIL
============================================================

Display available real metadata:

backdrop
poster
title
original title
year
runtime
genres
rating
certification
overview

Actions:

Play
Resume
Favorite
Watchlist
Mark Watched
Refresh Metadata

Sections:

Cast
Crew
Similar Media
Local Files
Provider Information

============================================================
30. TV SHOWS
============================================================

Display:

poster
title
year
rating
progress

Details:

backdrop
poster
overview
genres
rating
cast
crew

Provide season selection and episode lists.

Episode information must come from actual database/provider
data.

============================================================
31. MUSIC
============================================================

Provide:

Albums
Artists
Tracks

Support:

scanning
metadata
search
sorting
album details
artist details
track playback

============================================================
32. PEOPLE
============================================================

People must originate from real metadata.

Person page may contain:

photo
name
department
biography
known-for information
movie credits
TV credits

Never create fake people.

============================================================
33. FAVORITES
============================================================

Persistent.

Support relevant media types.

Add/remove must update the UI immediately and persist.

============================================================
34. WATCHLIST
============================================================

Persistent.

Support relevant media types.

Add/remove must update the UI immediately and persist.

============================================================
35. HISTORY
============================================================

Store real playback history.

Fields include:

media
episode where applicable
timestamp
position
duration
completion

Avoid meaningless duplicate records.

============================================================
36. COLLECTIONS
============================================================

Support:

Create
Rename
Delete
Add media
Remove media
Open collection
Play media

Everything must persist.

============================================================
37. RECOMMENDATIONS
============================================================

Use real data such as:

watch history
favorites
genres
ratings where available
actors
directors
completion patterns

Provide useful recommendation sections.

Do not claim AI functionality unless actual AI functionality
exists.

Never fabricate recommendations.

============================================================
38. STATISTICS
============================================================

Use real values.

Provide statistics for available library data such as:

Movies
TV Shows
Episodes
Artists
Albums
Tracks
People
Files
Watch Time
Watched items
Favorites
Watchlist
Sessions
Missing Files
Artwork Cached

Charts must use real data.

============================================================
39. PLAYER ARCHITECTURE
============================================================

Primary player engine:

MPV

Normal playback must be integrated into the JMDB desktop
experience.

Do not open a separate MPV window for normal playback.

Preferred communication:

Renderer
→ secure preload
→ Electron main
→ MPV

MPV integration must support BOTH:

Linux
Windows

Executable discovery must be platform-aware.

============================================================
40. PLAYER FORMATS
============================================================

Support formats and codecs according to the capabilities
of the installed MPV/build.

Target support includes:

H.264
H.265 / HEVC
HEVC 10-bit
AV1
MKV
MP4
common video formats
common audio formats

Support where available:

DTS
TrueHD

Support:

embedded subtitles
external subtitles
multiple audio tracks
multiple subtitle tracks

Never claim a codec is supported if the installed runtime
cannot actually decode it.

============================================================
41. PLAYER CONTROLS
============================================================

Provide:

Play/Pause
Previous
Next
Seek
Timeline
Buffering state
Volume
Mute
Speed
Audio Track
Subtitle Track
Subtitle Delay
Audio Delay
Fullscreen
Aspect Ratio
Queue
Autoplay Next

Controls should auto-hide where appropriate.

Mouse and keyboard supported.

============================================================
42. PLAYBACK PERSISTENCE
============================================================

Persist:

media ID
position
duration
timestamp
completion

Resume must survive application restart.

Continue Watching must use actual saved state.

Watched threshold must be configurable.

Resume threshold must be configurable.

============================================================
43. AUTOPLAY
============================================================

When applicable after media completion:

display the next item.

Show countdown.

Provide:

Play Now
Cancel

Persist completion before starting the next item.

============================================================
44. BROWSER HUB
============================================================

Browser Hub MUST be a REAL embedded Chromium browser.

The iframe implementation is NOT acceptable.

Use an appropriate Electron architecture based on:

WebContents
WebContentsView
or another supported native Chromium embedding mechanism.

The browser must actually render normal websites inside JMDB.

Required:

Tabs
New Tab
Close Tab
Switch Tab
Address Bar
Search
Back
Forward
Reload
Stop
Loading Indicator
Title
Favicon
Scrolling
Clicking
Text Input
Keyboard Input
Copy
Paste
Select
Context Menu
Open Link New Tab
Open Externally
Find
Zoom
Downloads
PDF
Cookies
JavaScript
Permissions
History
Clear Browser Data
External Browser

============================================================
45. BROWSER TAB SYSTEM
============================================================

Each tab must have:

unique ID
URL
title
favicon
loading state
web contents/view
session/profile information
zoom state

Support:

create
activate
close
restore
duplicate

Keyboard:

Ctrl+T
Ctrl+W
Ctrl+Shift+T
Ctrl+Tab
Ctrl+Shift+Tab

============================================================
46. BROWSER NAVIGATION
============================================================

Address bar accepts:

URL

or

search query.

Search engine is configurable.

Support:

Back
Forward
Reload
Stop

Display loading state.

Handle navigation failures honestly.

============================================================
47. BROWSER CONTEXT MENU
============================================================

Provide appropriate browser context actions:

Back
Forward
Reload
Copy
Paste
Select All
Open Link
Open Link in New Tab
Open Link Externally
Save Image
Copy Image
Inspect where appropriate

Only expose valid actions for the current context.

============================================================
48. BROWSER PERMISSIONS
============================================================

Implement controlled permission handling for:

Notifications
Geolocation
Camera
Microphone
Clipboard
Downloads
Popups
Fullscreen
Media playback
Autoplay
JavaScript
Cookies/storage where applicable
PDF
Other relevant Chromium permissions

Permission states:

Default
Ask
Allow
Deny

Permissions should be origin-aware where applicable.

Never automatically grant sensitive permissions globally.

============================================================
49. BROWSER PRIVACY
============================================================

Support:

Cookies
Cache
Browsing history
Passwords where Chromium supports them
Autofill
Site settings

Do Not Track.

Safe Browsing where supported.

Accept cookies.

On Exit:

Clear cache
Clear cookies
Clear history

according to user settings.

============================================================
50. CLEAR BROWSING DATA
============================================================

Support:

Cached images/files
Cookies/site data
Browsing history
Passwords
Autofill
Site settings

Time ranges:

Last hour
Last 24 hours
Last 7 days
Last 4 weeks
All time

The operation must actually clear Chromium data.

============================================================
51. BROWSER SETTINGS
============================================================

Sections:

General
Search Engine
Appearance
Privacy & Security
Content Settings
Downloads
Language
Shortcuts
About

All settings must persist and affect real browser behavior.

============================================================
52. BROWSER DOWNLOAD MANAGER
============================================================

Use real Electron download events.

Display:

filename
progress
percentage
speed
ETA
status

Support:

Pause
Resume
Cancel
Retry where possible
Show in Folder

The controls must operate on the real download.

Persist download information appropriately.

============================================================
53. EXTERNAL BROWSER FALLBACK
============================================================

Provide controlled external-browser fallback.

Detect installed browsers separately on:

Linux
Windows

Prefer a supported installed Chromium-based browser where
appropriate.

If no suitable browser exists:

show a clear actionable error.

Never silently fail.

============================================================
54. SERVICES
============================================================

Required:

YouTube
Telegram
Spotify
TV Time

Each service must provide:

official recognizable logo
service name
description
Open in Browser Hub

Use official service URLs.

Do not invent APIs.

TV Time is browser-based.

Spotify is browser/web based.

YouTube is browser/web based.

Telegram uses Telegram Web.

============================================================
55. SERVICE BRANDING
============================================================

Use recognizable official-style vector/SVG branding where
legally and technically appropriate.

Do not replace service branding with unrelated generic icons.

Do not use screenshots instead of logos.

============================================================
56. SECURITY MODEL
============================================================

Renderer:

NO nodeIntegration.

Use:

contextIsolation.

Secure preload.

Expose only explicit APIs.

IPC channels must be allow-listed.

Validate all arguments.

Reject malformed requests.

Do not allow renderer to execute arbitrary shell commands.

Do not allow arbitrary filesystem access.

Do not expose secrets.

============================================================
57. URL SECURITY
============================================================

Browser navigation must validate URLs.

Handle safely:

http
https
file where explicitly required
about pages where required

Reject or safely handle dangerous protocols.

External application launching must use an allow-listed
protocol policy.

Never execute arbitrary URLs through shell commands.

============================================================
58. FILESYSTEM SECURITY
============================================================

Validate library paths.

Do not accidentally scan system directories.

Do not follow dangerous symlink loops indefinitely.

Handle:

permission denied
broken symlink
missing directory
unreadable file

safely.

Validation must work on BOTH Linux and Windows.

============================================================
59. PROCESS SECURITY
============================================================

MPV and other child processes must:

start safely
stop safely
restart safely
detect crashes
capture stderr/logs
avoid orphan processes

Electron child-process execution must use validated executable
paths.

Never execute arbitrary user-provided command strings.

============================================================
60. SETTINGS PERSISTENCE
============================================================

Persist:

Theme
Playback preferences
Browser preferences
Library locations
Metadata configuration
Notification preferences
Player configuration
Download settings

Changes must survive restart on Linux and Windows.

============================================================
61. ERROR HANDLING
============================================================

Handle:

backend unavailable
database failure
metadata failure
missing file
MPV unavailable
Electron IPC failure
download failure
invalid URL
permission denial
network failure
player failure
browser navigation failure

Every user-facing error should explain:

What happened
Possible reason
Suggested action

Never show unexplained blank screens.

============================================================
62. EMPTY STATES
============================================================

Every empty page must have:

Icon/visual
Title
Explanation
Relevant action

Examples should describe STATES, not specific media titles.

Examples:

No media available
No TV content available
No music available
No people available
No favorites
No watchlist
No history
No collections
No recommendations

Never populate production UI with sample movies, shows,
artists or fake statistics.

============================================================
63. PERFORMANCE
============================================================

Use:

lazy artwork loading
image caching
database indexes
pagination/virtualization where necessary
debounced search
background scanning
background metadata
background artwork downloads

The application must remain usable on modest hardware.

============================================================
64. ACCESSIBILITY
============================================================

Support:

keyboard navigation
visible focus
accessible labels
tooltips
adequate contrast
logical tab order
keyboard shortcuts

Do not hide essential controls behind hover only.

============================================================
65. VISUAL DESIGN
============================================================

Use:

8px spacing system
moderate corner radius
subtle borders
subtle shadows
consistent typography
consistent icons
consistent cards
consistent dialogs

Avoid:

excessive gradients
excessive glow
excessive animation
visual clutter

Poster/artwork should be visually important where available.

============================================================
66. HOME VISUAL HIERARCHY
============================================================

Top:

cinematic Hero.

Then:

Continue Watching
Recently Added
New Episodes
Favorites
Recommended
Statistics

Horizontal content rails should scroll naturally.

Do not turn the entire application into a giant wall of cards.

============================================================
67. MOVIE CARD
============================================================

Normal:

poster
title
year
rating

Hover:

subtle enlargement
dark overlay
Play
Details
Favorite
Watchlist

Do not cause layout jumps.

============================================================
68. PLAYER UI
============================================================

Cinematic video area.

Bottom controls:

timeline

Left:

Previous
Play/Pause
Next

Center:

time

Right:

Volume
Audio
Subtitle
Speed
Settings
Fullscreen

Controls auto-hide appropriately.

============================================================
69. BROWSER UI
============================================================

Tabs at top.

Toolbar below.

Address bar.

Browser content fills available space.

Downloads appear in the browser download UI.

Browser settings should feel like a real desktop browser.

============================================================
70. RESPONSIVE DESKTOP
============================================================

Test application layouts at:

1280x720
1366x768
1920x1080
2560x1440

Support both Linux and Windows window behavior.

Sidebar remains usable.

Content scrolls.

Cards adapt.

Browser remains usable.

Player remains usable.

============================================================
71. LOGGING
============================================================

Create structured logs.

Log:

startup
shutdown
scanner
metadata
artwork
player
browser
downloads
IPC
errors

Do not log secrets.

Use platform-appropriate log locations.

============================================================
72. HEALTH / DIAGNOSTICS
============================================================

Provide diagnostics for:

Database
Python backend
Electron
Node.js
MPV
VLC
FFmpeg where applicable
Browser subsystem
Network
Configured providers
Library
Storage
Operating system

Use:

PASS
WARN
FAIL

with useful explanations.

============================================================
73. TESTING STRATEGY
============================================================

Implement:

Unit tests
Integration tests
API tests
IPC tests
Browser tests
Player tests
Database tests
Scanner tests
Metadata tests
UI tests
End-to-end tests

Test both:

Linux
Windows

where platform-specific behavior exists.

Do not only test that functions return values.

Test actual behavior.

============================================================
74. DATABASE TESTS
============================================================

Verify:

migration
insert
update
delete
foreign keys
indexes
duplicate prevention
restart persistence
missing-file handling
transaction rollback
data integrity

============================================================
75. SCANNER TESTS
============================================================

Verify:

movie discovery
TV discovery
episode discovery
music discovery
duplicate prevention
repeated scans
permission failures
missing directories
cancellation
large libraries
cross-platform path handling

Do not use hard-coded real media examples in production code.

============================================================
76. PLAYBACK TESTS
============================================================

Verify:

player startup
play
pause
seek
volume
audio track
subtitle
fullscreen
position save
resume
completion
autoplay
next item
restart persistence
player failure
fallback behavior

============================================================
77. BROWSER TESTS
============================================================

Verify:

new tab
close tab
switch tab
URL navigation
search
back
forward
reload
stop
title
favicon
scroll
input
context menu
new-tab links
external links
find
zoom
downloads
pause
resume
permissions
cookies
history
clear browsing data
settings persistence

============================================================
78. SERVICES TESTS
============================================================

Verify:

YouTube opens
Telegram opens
Spotify opens
TV Time opens

Verify services can open through Browser Hub.

Verify branding.

Verify graceful failure when network is unavailable.

============================================================
79. SECURITY TESTS
============================================================

Verify:

nodeIntegration disabled
contextIsolation enabled
IPC validation
malformed IPC rejected
unsafe URLs rejected
secrets unavailable to webpages
unsafe filesystem access rejected
permission handling
child-process validation

Test platform-specific security behavior on Linux and Windows.

============================================================
80. END-TO-END ACCEPTANCE
============================================================

Fresh installation:

Launch JMDB.

Application opens successfully.

Home appears.

Configure application.

Add a media location.

Scan.

Library populates with actual local media.

Open a media item.

Metadata appears when configured and available.

Artwork appears when available.

Play.

Pause.

Seek.

Exit.

Reopen.

Resume.

Favorite.

Verify Favorites.

Add Watchlist.

Verify Watchlist.

Open TV content.

Open Show.

Open Season.

Open Episode.

Play.

Finish.

Verify next item behavior.

Open History.

Verify playback state.

Open People.

Open person details where metadata exists.

Open Collections.

Create collection.

Add media.

Open Services.

Open YouTube.

Open Telegram.

Open Spotify.

Open TV Time.

Open Browser Hub.

Create multiple tabs.

Navigate.

Search.

Download.

Pause download.

Resume download.

Open Browser Settings.

Change settings.

Clear browsing data.

Change theme.

Restart JMDB.

Verify persistence.

Run the same relevant acceptance tests on:

Linux

and

Windows.

============================================================
81. REAL-DATA RULE
============================================================

Never hard-code:

movie counts
TV counts
music counts
people
ratings
recommendations
watch history
favorites
watchlist
statistics
progress
download progress
browser state

All must come from:

actual runtime data
actual database
actual filesystem
actual provider responses
actual browser state
actual player state

============================================================
82. NO PLACEHOLDER RULE
============================================================

Do not use in production:

Lorem ipsum
fake statistics
fake cards
fake progress
fake player
fake browser
fake services
fake metadata
fake API responses
dead buttons
sample media titles
sample TV titles
sample artist names

Test fixtures are allowed ONLY inside tests.

============================================================
83. INSTALLATION EXPERIENCE
============================================================

Provide installation for BOTH official platforms.

Linux:

Provide a clear setup/build process.

Windows:

Provide a clear setup/build process.

Check:

Python
Node
npm
Electron dependencies
MPV
VLC
FFmpeg where applicable

Create useful diagnostics when something is missing.

Do not fail with unexplained tracebacks.

============================================================
84. FIRST RUN EXPERIENCE
============================================================

First launch should guide the user through:

Application setup
Theme
Library Location
Metadata provider configuration
Player detection
Browser defaults

Optional online services must be skippable.

The application must remain useful offline.

============================================================
85. OFFLINE BEHAVIOR
============================================================

Without internet:

Local library must remain usable.

Playback must remain usable.

Favorites must remain usable.

Watchlist must remain usable.

Collections must remain usable.

History must remain usable.

Browser must display normal network failure behavior.

Metadata operations must report network unavailability.

============================================================
86. NETWORK FAILURE
============================================================

Never freeze the application because an online provider fails.

Use:

timeouts
retry
fallback
clear error states

Do not block the UI indefinitely.

============================================================
87. DATA RECOVERY
============================================================

Database operations must be transactional.

Scanner interruption must not corrupt the database.

Metadata refresh failure must preserve existing metadata.

Artwork failure must preserve media.

Player crash must preserve playback position as far as
reasonably possible.

============================================================
88. APPLICATION LIFECYCLE
============================================================

Handle:

startup
backend startup
database initialization
window creation
browser initialization
player initialization
shutdown
restart
unexpected player exit
backend failure

Shutdown must clean up child processes on both Linux and
Windows.

============================================================
89. BACKEND HEALTH
============================================================

Expose:

GET /api/health

Return real component state.

Do not report healthy when the database/backend is broken.

============================================================
90. API DESIGN
============================================================

Use REST or clearly defined local RPC endpoints.

Group endpoints logically:

/api/media
/api/movies
/api/tv
/api/music
/api/people
/api/playback
/api/history
/api/favorites
/api/watchlist
/api/collections
/api/recommendations
/api/statistics
/api/scanner
/api/metadata
/api/settings

Use validation models.

Return structured errors.

============================================================
91. IPC DESIGN
============================================================

Define explicit IPC contracts.

Examples:

browser:create-tab
browser:close-tab
browser:navigate
browser:back
browser:forward
browser:reload
browser:find
browser:set-zoom

download:list
download:pause
download:resume
download:cancel
download:retry

player:open
player:play
player:pause
player:seek
player:set-volume
player:set-audio-track
player:set-subtitle-track
player:fullscreen

settings:get
settings:set

All IPC channels must be explicit and validated.

============================================================
92. UI STATE MANAGEMENT
============================================================

Centralize application state.

Separate:

library state
player state
browser state
settings state
user preference state

Avoid duplicated competing sources of truth.

============================================================
93. SEARCH
============================================================

Global search searches:

Movies
TV Shows
Episodes
People
Artists
Albums
Tracks

Results grouped by type.

Keyboard:

Ctrl+K

Enter opens selected result.

Escape closes search.

============================================================
94. KEYBOARD SHORTCUTS
============================================================

Global/browser:

Ctrl+K
Ctrl+L
Ctrl+T
Ctrl+W
Ctrl+Shift+T
Ctrl+Tab
Ctrl+Shift+Tab
Ctrl+R
Ctrl+F
Ctrl++
Ctrl+-
Ctrl+0
F11

Player shortcuts must be documented.

Use platform-appropriate modifier behavior where necessary.

============================================================
95. NOTIFICATIONS
============================================================

Support:

Scan started
Scan complete
Scan failed
Metadata refreshed
Artwork updated
Download completed
Download failed
Playback error
Permission request

Notifications must not become intrusive.

============================================================
96. ABOUT
============================================================

Display:

JMDB
Johnny's Media Database
Version 1.0.0

Built with:

Electron
Chromium
Node.js
Python

Display detected versions where useful.

============================================================
97. DOCUMENTATION
============================================================

Create documentation for:

Architecture
Database
Browser
Player
Metadata
Security
Testing
Installation
Troubleshooting
Linux
Windows
Packaging

Documentation must describe the ACTUAL implementation.

============================================================
98. CODE QUALITY
============================================================

Use:

clear naming
small focused modules
validation
error handling
logging
useful comments
platform abstractions

Avoid:

giant files
giant functions
duplicated logic
magic constants
hard-coded paths
hard-coded secrets
platform assumptions

============================================================
99. BUILD / PACKAGING
============================================================

Provide:

Development mode
Production build

Linux:

AppImage or equivalent production package.

Windows:

NSIS installer and/or portable package.

Packaging must include all required runtime resources.

The packaged application must NOT depend on the source tree.

Test packaged startup.

============================================================
100. FINAL QA / DEFINITION OF DONE
============================================================

Before declaring JMDB complete:

Run all automated tests.

Run relevant manual acceptance tests.

Verify clean startup.

Verify restart persistence.

Verify real media scanning.

Verify real metadata.

Verify real artwork.

Verify real playback.

Verify MPV detection.

Verify browser navigation.

Verify browser tabs.

Verify real downloads.

Verify permissions.

Verify browser settings.

Verify privacy controls.

Verify services.

Verify themes.

Verify database integrity.

Verify Linux behavior.

Verify Windows behavior.

Verify production packaging.

============================================================
FINAL ACCEPTANCE CHECKLIST
============================================================

[ ] Application launches on Linux
[ ] Application launches on Windows
[ ] Database works
[ ] Migrations work
[ ] Library scanning works
[ ] Movies work
[ ] TV Shows work
[ ] Episodes work
[ ] Music works
[ ] People work
[ ] Metadata works
[ ] Artwork works
[ ] Search works
[ ] Playback works
[ ] MPV detection works
[ ] MPV integration works
[ ] Resume works
[ ] Autoplay works
[ ] History works
[ ] Favorites work
[ ] Watchlist works
[ ] Collections work
[ ] Recommendations work
[ ] Statistics work
[ ] Services work
[ ] Browser is real Chromium
[ ] Browser is NOT an iframe
[ ] Browser tabs work
[ ] Navigation works
[ ] Scrolling works
[ ] Clicking works
[ ] Text input works
[ ] Browser settings work
[ ] Permissions work
[ ] Downloads work
[ ] Privacy controls work
[ ] External browser fallback works
[ ] Themes work
[ ] Settings persist
[ ] Security model passes
[ ] Automated tests pass
[ ] Manual acceptance passes
[ ] Restart persistence passes
[ ] Linux packaging works
[ ] Windows packaging works
[ ] No critical known defects remain

============================================================
FINAL DELIVERY REQUIREMENT
============================================================

At the end provide a concise but complete engineering report:

1. Architecture summary
2. Complete feature list
3. Complete folder structure
4. Dependency list
5. System dependency list
6. Linux implementation
7. Windows implementation
8. Permission/security implementation
9. Database schema summary
10. API summary
11. IPC summary
12. Browser implementation
13. Player implementation
14. Services implementation
15. Scanner implementation
16. Metadata implementation
17. Settings implementation
18. Test counts
19. Exact test results
20. Linux acceptance results
21. Windows acceptance results
22. Packaging results
23. Known limitations
24. Required user configuration
25. Installation instructions
26. Run instructions
27. Diagnostic instructions

For every remaining limitation state:

WHAT
WHY
WORKAROUND

Never hide limitations.

============================================================
ABSOLUTE RULES
============================================================

1. Linux and Windows are BOTH official v1.0.0 targets.

2. Do not build Linux-only functionality and call the project
   cross-platform.

3. Do not build Windows-only functionality and call the project
   cross-platform.

4. Do not hard-code Linux paths into Windows code.

5. Do not hard-code Windows paths into Linux code.

6. Do not use an iframe as the Browser Hub.

7. Do not use HTML5 video as the primary player.

8. Do not create fake controls.

9. Do not create fake progress.

10. Do not create fake statistics.

11. Do not create fake metadata.

12. Do not create fake services.

13. Do not hard-code example movie, TV, music or person data.

14. Do not invent APIs.

15. Do not leave dead buttons.

16. Do not leave dummy tests.

17. Do not claim a feature is complete without testing it.

18. Do not stop at documentation.

19. Do not stop at a visual prototype.

20. Do not stop when the code merely compiles.

============================================================
FINAL COMMANDMENT
============================================================

BUILD THE ACTUAL JMDB.

Build it as a real desktop application for:

LINUX + WINDOWS

from zero to 100%.

Inspect the existing project first.

Reuse good existing code.

Replace incomplete implementations where necessary.

Implement the missing functionality.

Wire every subsystem together.

Test every major feature.

Fix every discovered failure.

Verify both operating systems.

Build the production packages.

Do not produce another partial prototype.

Do not produce another incomplete shell.

Do not leave an iframe Browser Hub.

Do not leave HTML5 video as the primary player.

Do not leave fake controls.

Do not leave dummy tests.

Do not leave undocumented critical limitations.

Do not use specific movie/show/music examples that could
confuse implementation.

Use generic technical descriptions and real runtime data.

The final result must be a coherent, secure, persistent,
professional desktop application called:

JMDB

Johnny's Media Database

VERSION 1.0.0

OFFICIAL TARGETS:

Linux Desktop
Windows Desktop

The application must feel finished.

============================================================
END OF MASTER BUILD SPECIFICATION
============================================================
