# Jazz Vinyl Guide

Collector-grade vinyl pressing guides for essential jazz albums.
Live at [jazzvinylguide.com](https://jazzvinylguide.com).

## Deployment (one-time setup)

### 1. Push to GitHub

Create a new public repository on GitHub named `jazzvinylguide`, then:

```bash
cd jazzvinylguide
git init
git add .
git commit -m "Initial site"
git remote add origin https://github.com/YOUR_USERNAME/jazzvinylguide.git
git branch -M main
git push -u origin main
```

### 2. Deploy on Netlify

1. Log in to [netlify.com](https://netlify.com)
2. Click **Add new site → Import an existing project**
3. Choose **GitHub** and select the `jazzvinylguide` repository
4. Build settings are pre-configured in `netlify.toml` — just click **Deploy**
5. Netlify will give you a URL like `https://random-name.netlify.app`

### 3. Connect your domain

1. In Netlify: **Site settings → Domain management → Add custom domain**
2. Enter `jazzvinylguide.com`
3. Netlify will show you two nameserver addresses (e.g. `dns1.p01.nsone.net`)
4. At your domain registrar, replace the existing nameservers with Netlify's
5. Wait 10–30 minutes — your site will be live at jazzvinylguide.com with HTTPS automatic

### 4. Enable the CMS (for contributors)

1. In Netlify: **Site settings → Identity → Enable Identity**
2. Under **Registration**: set to **Invite only**
3. Under **Services → Git Gateway**: click **Enable Git Gateway**
4. Update `admin/config.yml`: replace `YOUR_GITHUB_USERNAME` with your actual username
5. Invite contributors via **Identity → Invite users**

Contributors can then edit content at `jazzvinylguide.com/admin`

## Adding a new album guide

Either:
- Use the CMS at `/admin` (no coding required)
- Or create a new file in `_albums/` following the existing format

## Local development

```bash
gem install bundler
bundle install
bundle exec jekyll serve
# → http://localhost:4000
```
