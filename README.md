# iCloud IMAP Cleanup

A safe and intelligent email cleanup tool for iCloud that automatically moves promotional emails, newsletters, and low-value messages to a review folder for later deletion.

## Features

- **Safe Mode**: Moves emails to a review folder instead of deleting them
- **Smart Detection**: Identifies promotional emails using List-Unsubscribe headers and subject keywords
- **Age-Based**: Only processes emails older than a configurable threshold (default: 1 year)
- **Whitelist Support**: Protects trusted senders from cleanup
- **Dry Run Mode**: Test what would be moved without making changes
- **Multi-Folder Support**: Scans multiple source folders (INBOX, Archive, etc.)
- **Financial Protection**: Never moves important financial documents
- **JSON Configuration**: Easy customization without code changes

## Requirements

- Python 3.9+
- iCloud account with app-specific password
- Standard library only (no external dependencies except `python-dotenv`)

## Quick Start

1. **Generate App-Specific Password**
   - Visit [https://appleid.apple.com/](https://appleid.apple.com/)
   - Generate an app-specific password for this script

2. **Set Environment Variables**
   ```powershell
   # Copy the example file and edit with your credentials
   copy .env.example .env
   
   # Then edit .env file with your actual credentials:
   # IMAP_USER=your_icloud_email@icloud.com
   # IMAP_PASS=your_app_specific_password
   ```

3. **Install Dependencies**
   ```powershell
   pip install python-dotenv
   ```

4. **Run in Test Mode**
   ```powershell
   python icloud_imap_cleanup.py
   ```
   The script runs in dry-run mode by default, showing what would be moved.

5. **Enable Live Mode**
   Edit `config.json` and set `"dry_run": false` to actually move emails.

## Project Files

- `icloud_imap_cleanup.py` - Main script
- `config.json` - Configuration file (auto-created with defaults)
- `config.local.json` - Personal config overrides (not tracked by Git)
- `config.local.example.json` - Template for local configuration
- `.env` - Your credentials (create from `.env.example`)
- `.env.example` - Template for environment variables
- `whitelist.txt` - Optional file for whitelisted senders
- `README.md` - This documentation

## Configuration

The script uses a two-tier configuration system:

1. **`config.json`** - Default/shared configuration (Git-tracked)
2. **`config.local.json`** - Personal overrides (Git-ignored)

### Git-Ready Setup

The default `config.json` contains safe, universal settings:
- **Conservative defaults** (dry_run: true, age_days: 365)
- **Basic English keywords** that work for most users
- **Empty delete_domains** array for you to populate
- **Standard iCloud settings** that work out of the box

### Personal Configuration Override

For personal settings that you don't want to commit to Git, create a `config.local.json` file:

```powershell
copy config.local.example.json config.local.json
# Edit config.local.json with your personal settings
```

The local config will override any settings from `config.json`. This is perfect for:
- Personal age thresholds
- Your specific delete domains
- Custom keywords for your language/region
- Enabling/disabling dry run mode

### Configuration File Structure

#### 1. Mail Settings
```json
"mail_settings": {
    "imap_host": "imap.mail.me.com",
    "imap_port": 993,
    "source_folders": ["INBOX", "Archive"],
    "target_folder": "Review/Delete"
}
```

#### 2. Cleanup Settings
```json
"cleanup_settings": {
    "age_days": 365,
    "dry_run": true,
    "verbose": true,
    "search_timeout": 30,
    "max_search_keywords": 10
}
```

- `age_days`: Only process emails older than this many days
- `dry_run`: If true, show what would be moved without actually moving
- `verbose`: Enable detailed logging
- `search_timeout`: IMAP search timeout in seconds (prevents hanging)
- `max_search_keywords`: Batch keywords into groups to improve performance

#### 3. Subject Keywords
Add or remove keywords that identify emails to be moved:
```json
"subject_keywords": [
    "unsubscribe",
    "newsletter",
    "promo",
    "promotion",
    "deal",
    "korting",
    "sale"
]
```

#### 4. Protect Keywords
Keywords that prevent emails from being moved (for important financial documents):
```json
"protect_keywords": [
    "factuur",
    "invoice",
    "bill",
    "tax",
    "refund"
]
```

#### 5. Whitelist Settings
```json
"whitelist_settings": {
    "whitelist_file": "whitelist.txt",
    "additional_whitelist": ["trusted@example.com", "important.domain.com"]
}
```

#### 6. Delete Domains
Automatically move emails from specific domains (useful for promotional/automated emails):
```json
"delete_domains": [
    "mail.degiro.com",
    "noreply.example.com",
    "updates.company.com"
]
```

### Customization Examples

### Personal Configuration Examples

These examples show what to put in your `config.local.json` file:

#### Enable Live Mode with Aggressive Cleanup
```json
{
    "cleanup_settings": {
        "age_days": 180,
        "dry_run": false,
        "verbose": true
    }
}
```

#### Add Dutch Keywords and Specific Domains
```json
{
    "subject_keywords": [
        "unsubscribe", "afmelden", "nieuwsbrief", "newsletter",
        "actie", "korting", "aanbieding", "sale", "promo",
        "bevestiging", "leveringsupdate", "tracking",
        "nieuwsbrief", "verzendbericht", "Wat vond u"
    ],
    "delete_domains": [
        "mail.degiro.com",
        "noreply.booking.com",
        "updates.linkedin.com"
    ]
}
```

## How It Works

1. **Connects** to iCloud IMAP using your credentials
2. **Scans** specified folders for emails older than the age threshold
3. **Identifies** promotional emails using:
   - List-Unsubscribe header presence
   - Subject line keywords
   - Specific sender domains
   - Subject line keywords
4. **Filters** out whitelisted senders and protected keywords
5. **Moves** matching emails to the review folder (or shows what would be moved in dry-run mode)

## Safety Features

- **Dry Run Mode**: Test safely before making changes
- **Age Protection**: Only touches old emails (configurable threshold)
- **Whitelist Support**: Protects trusted senders
- **Financial Protection**: Never moves emails with financial keywords
- **Flagged Email Protection**: Skips starred/flagged messages
- **Review Folder**: Moves instead of deleting for easy recovery

## Customization Tips

1. **Add New Subject Keywords**: Include terms specific to your language/region
2. **Add Delete Domains**: Specify domains that send unwanted emails (e.g., `"mail.degiro.com"`)
3. **Adjust Age Threshold**: 
   - 180 days for aggressive cleanup
   - 365 days for balanced approach
   - 730 days for conservative cleanup
4. **Enable/Disable Dry Run**: Always test with `"dry_run": true` first
5. **Add Source Folders**: Include other folders like "Sent", "Spam"
6. **Customize Target Folder**: Choose your preferred destination

## Important Notes

- The script will create `config.json` with default values if it doesn't exist
- Use `config.local.json` for personal settings that won't be committed to Git
- Always test with `"dry_run": true` first to see what would be moved
- Environment variables `IMAP_USER` and `IMAP_PASS` are still used for login credentials
- The `whitelist.txt` file is still supported alongside the JSON configuration
- Moved emails can be easily restored from the review folder if needed
- Local config overrides take precedence over settings in `config.json`

## Troubleshooting

- **Login Issues**: Ensure you're using an app-specific password, not your regular iCloud password
- **Folder Not Found**: The target folder will be created automatically if it doesn't exist
- **No Emails Found**: Check your age threshold and keyword settings
- **Permission Errors**: Ensure your app-specific password has the correct permissions

## License

This project is open source. Feel free to modify and distribute as needed.