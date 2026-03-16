# Cloudflare Mail Setup Guide

This guide focuses on one thing only:

how to set up `Cloudflare domain mail + a simple mail API` so it works smoothly with our `tavily-key-generator`.

If you want the shortest possible summary first, remember this:

> Cloudflare receives the mail. Our own API exposes the mail content to the project.

---

## 1. What the project actually needs

It is easy to misunderstand the Cloudflare flow at first.

A lot of people assume one of these:

- the project talks directly to a built-in Cloudflare inbox API
- once Email Routing is enabled in Cloudflare, the project can read messages automatically

Neither is true for our current implementation.

What the project really does is:

1. generate a random mailbox such as `tavily-ab12cd34@tvmail.example.com`
2. use that mailbox during Tavily signup
3. wait for Tavily to send the verification email
4. poll your own mail API:

```text
GET {EMAIL_API_URL}/messages?address=random-mailbox
Authorization: Bearer {EMAIL_API_TOKEN}
```

Then it reads:

- `subject`
- `text`
- `html`

and extracts the 6-digit code.

So the project needs two separate capabilities:

1. **a way to receive mail for your domain**
2. **a way to read that mail over HTTP**

Cloudflare solves the first part very well.  
We add a thin API layer for the second part.

---

## 2. The recommended architecture

The whole flow should look like this:

```text
Tavily sends the verification email
        ↓
tavily-random-string@your-domain
        ↓
Cloudflare Email Routing receives it
        ↓
Catch-all rule matches
        ↓
Mail is sent to an Email Worker
        ↓
The Worker parses the message and stores it in D1
        ↓
Our project requests /messages?address=...
        ↓
The project reads the message and extracts the code
```

Each layer has a single job:

- `Email Routing` receives mail
- `Worker` processes mail
- `D1` stores mail
- `API` returns mail to the project

---

## 3. Why a subdomain is usually the safest choice

If your main domain is already used by a real mailbox provider such as:

- Google Workspace
- Zoho Mail
- Outlook / Microsoft 365
- any other business mail service

then the safest option is:

**do not reuse the same mail domain for this automation flow.**

Instead, create a dedicated subdomain such as:

- `tvmail.example.com`
- `keys.example.com`
- `verify.example.com`

Why this is better:

1. it does not interfere with your normal business mail
2. the DNS and routing setup stays much cleaner
3. troubleshooting becomes much easier

In practice, this setup works best:

- your main domain stays untouched for normal mail
- your subdomain is used only for `tavily-key-generator`

---

## 4. What you should prepare first

Before you start, make sure you have:

1. a domain already managed by Cloudflare
2. access to the Cloudflare Dashboard
3. a chosen domain or subdomain for verification emails
4. willingness to deploy one small Cloudflare Worker
5. `node`, `npm`, and `wrangler` available locally

If `wrangler` is not installed yet:

```bash
npm install -g wrangler
```

Then log in:

```bash
wrangler login
```

---

## 5. Step 1: Put your domain or subdomain on Cloudflare

If your domain is not on Cloudflare yet:

1. log in to Cloudflare
2. click `Add a site`
3. add your domain
4. update the nameservers
5. wait until the zone becomes `Active`

If the domain is already managed by Cloudflare, you can move on.

If you want to use a dedicated subdomain, decide on it now. For example:

```text
tvmail.example.com
```

This exact value will later become your `EMAIL_DOMAIN`.

---

## 6. Step 2: Enable Email Routing

Open:

```text
Cloudflare Dashboard
-> your domain
-> Email
-> Email Routing
```

The first time you open it, Cloudflare usually shows a setup flow.

Follow it and let Cloudflare enable Email Routing and add the required DNS records.

These records usually include:

- `MX`
- `TXT`

Pay attention to these points:

### 1. Avoid existing MX conflicts

If the same domain is already being used by another mail provider, Cloudflare may report a conflict.

In plain language:

- if the domain already runs a normal mailbox service, do not force this setup onto it
- a dedicated subdomain is usually the cleanest solution

### 2. Fix SPF warnings early

If Cloudflare shows SPF problems, do not ignore them.

A domain should normally have one valid SPF entry path.  
Multiple SPF records often lead to delivery or verification issues.

### 3. Leave Cloudflare-managed Email Routing DNS records alone

Once Email Routing is enabled and working, avoid manually editing the mail records Cloudflare created for it.

---

## 7. Step 3: Enable Catch-all

This is the most important step for our project.

Why?

Because our project does not use one fixed mailbox.  
It creates random addresses like:

```text
tavily-a1b2c3d4@tvmail.example.com
tavily-z9y8x7w6@tvmail.example.com
```

You cannot pre-create every possible mailbox by hand.

The correct approach is:

**enable Catch-all so every random address can be received.**

How to do it:

1. go to `Email Routing`
2. open `Routes`
3. find `Catch-all address`
4. enable it
5. set the action to send mail to a `Worker`

Once Catch-all is active, every address on that domain without a dedicated route will still be handled.

That is exactly what this project needs.

---

## 8. Step 4: Send mail to a Worker, not to a normal mailbox

Cloudflare Email Routing gives you different action types, for example:

- forward to a normal mailbox
- send to a Worker

For our project, the best option is:

**send mail directly to a Worker.**

Why this is better:

- no IMAP or POP3 setup is needed
- no mailbox login automation is needed
- delays are lower
- the data shape stays under our control

So the most practical route is:

```text
Catch-all -> Send to Worker
```

---

## 9. Step 5: Create a dedicated mail Worker project

Run this locally:

```bash
npm create cloudflare@latest tavily-mail-api
cd tavily-mail-api
npm i postal-mime
```

We use `postal-mime` because Cloudflare gives the Worker a raw email message.  
We want to parse it into a structure that is easy for the project to consume:

- subject
- plain text
- HTML

---

## 10. Step 6: Create a D1 database

Create the database:

```bash
npx wrangler d1 create tavily_mail
```

Save the returned `database_id`.  
You will need it in `wrangler.toml`.

Then create `schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  address TEXT NOT NULL,
  subject TEXT,
  text TEXT,
  html TEXT,
  received_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_address_time
ON messages(address, received_at DESC);
```

Apply the schema:

```bash
npx wrangler d1 execute tavily_mail --file=schema.sql
```

This table is enough for the current project flow.

Field meanings:

- `id`: unique message identifier
- `address`: recipient address, the random mailbox generated by the project
- `subject`: email subject
- `text`: plain-text body
- `html`: HTML body
- `received_at`: receive timestamp, used for ordering

---

## 11. Step 7: Add the Worker code

Put this minimal implementation in `src/index.ts`:

```ts
import PostalMime from "postal-mime";

export interface Env {
  DB: D1Database;
  API_TOKEN: string;
}

function unauthorized() {
  return new Response("Unauthorized", { status: 401 });
}

function checkAuth(req: Request, env: Env) {
  const auth = req.headers.get("Authorization") || "";
  return auth === `Bearer ${env.API_TOKEN}`;
}

export default {
  async email(message: ForwardableEmailMessage, env: Env) {
    const parsed = await new PostalMime().parse(message.raw);
    const id =
      parsed.messageId ||
      `${String(message.to).toLowerCase()}-${Date.now()}-${crypto.randomUUID()}`;

    await env.DB.prepare(
      `INSERT OR REPLACE INTO messages
       (id, address, subject, text, html, received_at)
       VALUES (?1, ?2, ?3, ?4, ?5, ?6)`
    )
      .bind(
        id,
        String(message.to).toLowerCase(),
        parsed.subject || "",
        parsed.text || "",
        typeof parsed.html === "string" ? parsed.html : "",
        Date.now()
      )
      .run();
  },

  async fetch(req: Request, env: Env) {
    if (!checkAuth(req, env)) {
      return unauthorized();
    }

    const url = new URL(req.url);

    if (req.method === "GET" && url.pathname === "/messages") {
      const address = (url.searchParams.get("address") || "").trim().toLowerCase();

      if (!address) {
        return Response.json(
          { error: "missing address" },
          { status: 400 }
        );
      }

      const result = await env.DB.prepare(
        `SELECT id, subject, text, html, received_at
         FROM messages
         WHERE address = ?1
         ORDER BY received_at DESC
         LIMIT 20`
      )
        .bind(address)
        .all();

      return Response.json({
        messages: (result.results || []).map((row: any) => ({
          id: row.id,
          subject: row.subject || "",
          text: row.text || "",
          html: row.html || "",
          received_at: row.received_at,
        })),
      });
    }

    return new Response("Not found", { status: 404 });
  },
};
```

This code does only two things:

### `email()`

When Cloudflare receives a message, it calls this handler.  
We parse the message and save it to D1.

### `fetch()`

When our project requests:

```text
/messages?address=some-random-mailbox
```

we return the latest messages for that address from D1.

---

## 12. Step 8: Configure `wrangler.toml`

Use a minimal config like this:

```toml
name = "tavily-mail-api"
main = "src/index.ts"
compatibility_date = "2026-03-16"

[[d1_databases]]
binding = "DB"
database_name = "tavily_mail"
database_id = "replace-with-your-d1-database-id"
```

Then set your own API token secret:

```bash
npx wrangler secret put API_TOKEN
```

Use a long random string, for example:

```text
your-super-long-random-token
```

This point is extremely important:

**this `API_TOKEN` is what you put into the project's `EMAIL_API_TOKEN`.**

It is **not**:

- a Cloudflare Global API Key
- a Cloudflare account token
- a Zone API token

It is only the Bearer token for your own Worker API.

---

## 13. Step 9: Deploy the Worker

Run:

```bash
npx wrangler deploy
```

After deployment, you will get a URL that looks like:

```text
https://tavily-mail-api.xxx.workers.dev
```

That URL becomes your:

```env
EMAIL_API_URL=...
```

---

## 14. Step 10: Route Catch-all to the Worker

Go back to Cloudflare:

```text
Email
-> Email Routing
-> Routes
```

Find `Catch-all address` and set its action to:

```text
Send to a Worker
```

Then select the Worker you just deployed.

At this point, the receiving flow is complete:

```text
mail sent to any random address
-> Cloudflare Catch-all matches
-> Worker receives it
-> Worker stores it in D1
-> the project reads it via /messages
```

---

## 15. Step 11: Fill in the project's `.env`

If you only use one domain:

```env
EMAIL_PROVIDER=cloudflare
EMAIL_API_URL=https://tavily-mail-api.xxx.workers.dev
EMAIL_API_TOKEN=the-api-token-you-created
EMAIL_DOMAIN=tvmail.example.com
```

If you want multiple domains and runtime selection:

```env
EMAIL_PROVIDER=cloudflare
EMAIL_API_URL=https://tavily-mail-api.xxx.workers.dev
EMAIL_API_TOKEN=the-api-token-you-created
EMAIL_DOMAINS=tvmail.example.com,keys.example.com
```

Here is what each variable means:

### `EMAIL_PROVIDER`

Always set:

```text
cloudflare
```

This tells the project to use the Cloudflare domain mail flow.

### `EMAIL_API_URL`

This must be your Worker API URL.

It is **not** a Cloudflare dashboard API endpoint.

### `EMAIL_API_TOKEN`

This must be your own Worker Bearer token.

It is **not** a Cloudflare platform key.

### `EMAIL_DOMAIN`

This is the mail domain suffix, for example:

```text
tvmail.example.com
```

The project will generate addresses like:

```text
tavily-random-string@tvmail.example.com
```

### `EMAIL_DOMAINS`

If you provide multiple domains, the launcher can let you choose one at runtime.

---

## 16. How mailbox generation works in this project

This detail matters a lot during setup.

The project does not log in to one fixed mailbox.  
Instead, it generates random addresses such as:

```text
tavily-abcdefgh@tvmail.example.com
```

That means:

- you do not need to pre-create each mailbox
- you do not need to add mailboxes one by one
- you only need Catch-all to receive every random address

This is why Catch-all is mandatory for this setup.

---

## 17. Step 12: Test the flow before running the project

Do not jump straight into the full registration flow yet.

It is much safer to validate the mail pipeline first.

### Test 1: Send one manual test email

Pick a random address that should match Catch-all, for example:

```text
test-123@tvmail.example.com
```

Send an email to it from another mailbox.

### Test 2: Query the API with `curl`

```bash
curl -H "Authorization: Bearer your-api-token" \
  "https://tavily-mail-api.xxx.workers.dev/messages?address=test-123@tvmail.example.com"
```

If you see:

- `messages`
- `subject`
- `text`
- `html`

then the mail path is working.

### Test 3: Run the project

```bash
python3 run.py
```

If the verification-code step continues automatically, the full Cloudflare mail setup is working.

---

## 18. Most common mistakes

These are the problems people hit most often.

### 1. Using a Cloudflare API key as `EMAIL_API_TOKEN`

That is wrong.

`EMAIL_API_TOKEN` must be the Bearer token for your own Worker API.

### 2. Forgetting to enable Catch-all

The project uses random mailbox names.  
Without Catch-all, those addresses usually receive nothing.

### 3. Putting the Worker URL into `EMAIL_DOMAIN`

That is also wrong.

- `EMAIL_DOMAIN` is the mail suffix
- `EMAIL_API_URL` is the Worker URL

### 4. Reusing a production mail domain that already has another mail service

This often creates MX and routing conflicts.

The safest fix is:

**use a dedicated subdomain.**

### 5. The API opens, but the project still finds no messages

Check these first:

1. is the `Authorization` token correct
2. does the queried `address` exactly match the recipient address
3. is the Worker really writing to D1
4. is Catch-all actually enabled
5. is the route action really `Send to Worker`

### 6. Cloudflare Email Routing looks unstable

Check for:

- conflicting MX records
- multiple SPF records
- manually edited DNS records that Cloudflare created for Email Routing

---

## 19. The simplest recommended deployment plan

If you want the most practical setup with the fewest surprises, do this:

1. create a dedicated subdomain, such as `tvmail.example.com`
2. enable Cloudflare Email Routing
3. enable Catch-all
4. set Catch-all to `Send to Worker`
5. let the Worker parse mail and store it in D1
6. expose `GET /messages?address=...`
7. fill the project `.env` with:

```env
EMAIL_PROVIDER=cloudflare
EMAIL_API_URL=your-worker-url
EMAIL_API_TOKEN=your-worker-bearer-token
EMAIL_DOMAIN=your-mail-domain
```

This matches the current project implementation cleanly and avoids extra rewrites.

---

## 20. The easiest mental model

If you want the plain-English explanation, think of it like this:

### Cloudflare is the front desk, the Worker is the clerk, D1 is the storage room, and the project is the person picking up the letter.

Each part does one job:

- Cloudflare receives all mail sent to your domain
- the Worker opens the message and records it
- D1 stores the message data
- the project asks for the latest message by mailbox address

Once that model is clear, the whole setup becomes much easier to reason about.

---

## 21. Quick configuration examples

### Single domain

```env
EMAIL_PROVIDER=cloudflare
EMAIL_API_URL=https://tavily-mail-api.xxx.workers.dev
EMAIL_API_TOKEN=your-super-long-random-token
EMAIL_DOMAIN=tvmail.example.com
```

### Multiple domains

```env
EMAIL_PROVIDER=cloudflare
EMAIL_API_URL=https://tavily-mail-api.xxx.workers.dev
EMAIL_API_TOKEN=your-super-long-random-token
EMAIL_DOMAINS=tvmail.example.com,keys.example.com
```

---

## 22. Official references

If you want to compare this guide against the official docs, these are the most relevant Cloudflare pages:

- [Enable Email Routing](https://developers.cloudflare.com/email-routing/get-started/enable-email-routing/)
- [Email Routing Addresses and Rules](https://developers.cloudflare.com/email-routing/setup/email-routing-addresses/)
- [Email Routing Subdomains](https://developers.cloudflare.com/email-routing/setup/subdomains/)
- [Email Routing DNS Records](https://developers.cloudflare.com/email-routing/setup/email-routing-dns-records/)
- [Enable Email Workers](https://developers.cloudflare.com/email-routing/email-workers/enable-email-workers/)
- [Email Workers Runtime API](https://developers.cloudflare.com/email-routing/email-workers/runtime-api/)
- [Troubleshooting SPF records](https://developers.cloudflare.com/email-routing/troubleshooting/email-routing-spf-records/)
- [Test Email Routing](https://developers.cloudflare.com/email-routing/get-started/test-email-routing/)

---

## 23. Final advice

If your goal is simply to get the project working, do not overbuild on day one.

Start with the minimum working stack:

1. one subdomain
2. one Catch-all route
3. one Worker
4. one D1 database
5. one `/messages` endpoint

Get that pipeline working first.

Then, if you want, you can improve it later with:

- multiple rotating domains
- message cleanup jobs
- retention policies
- dashboards
- monitoring

That order is usually the fastest and least frustrating path.
