# MongoDB Atlas – Database Connect Avataniki (Step-by-Step)

**Common errors:**
- `querySrv ECONNREFUSED` → SRV DNS block; use `MONGO_URI_STANDARD` (direct connection).
- **"IP that isn't whitelisted"** → Atlas lo na IP add cheyali (Step 2). Add chesina kuda error unte → [IP add chesina kuda fail aithe](#ip-add-chesina-kuda-connection-fail)

---

## Step 1: MongoDB Atlas lo login

1. Browser lo open: **https://cloud.mongodb.com**
2. Na **Atlas account** tho login (ledhu ante "Try Free" tho sign up).

---

## Step 2: Network Access lo na IP allow cheyi

Atlas by default **na IP allow cheyadu** – so connection block avuthundi.

1. Left side menu lo **"Network Access"** click cheyi.
2. **"Add IP Address"** (green button) click cheyi.
3. **Option A (easy):**  
   - **"Allow Access from Anywhere"** click cheyi.  
   - Itho `0.0.0.0/0` add avuthundi (development kosam safe).
4. **Option B (secure):**  
   - **"Add Current IP Address"** click cheyi (na computer IP add avuthundi).
5. **"Confirm"** click cheyi.
6. 1–2 minutes wait cheyi – status **"Active"** ravali.

---

## Step 3: Cluster pause lo unte Resume cheyi

Free tier lo cluster **inactivity tarvata auto pause** avuthundi.

1. Left side **"Database"** (or "Database Deployments") click cheyi.
2. Na cluster **"cluster0"** (sfxte1d) list lo chudu.
3. **"Paused"** ane word unte:
   - Cluster name click cheyi → **"Resume"** button click cheyi.
4. Resume ayyaka 1–2 minutes wait cheyi.

---

## Step 4: Database user & password correct ga check cheyi

1. Left side **"Database Access"** click cheyi.
2. Na project lo **user** (e.g. `team_10`) unte click cheyi.
3. **"Edit"** → **"Edit Password"**.
4. Password **same** use chestunnava ani confirm cheyi (`.env` lo `MONGO_URI` lo unna password).
5. Password lo **special characters** unte (e.g. `@`, `#`, `:`):
   - Atlas lo password simple ga set cheyi (letters + numbers only), **or**
   - `.env` lo password **URL-encoded** pettali.  
     Example: `pass@word` → `pass%40word`

---

## Step 5: Connection string copy chesi `.env` lo pettuko

1. **"Database"** → na cluster **"Connect"** click cheyi.
2. **"Connect using MongoDB Compass"** or **"Drivers"** select cheyi.
3. Connection string copy cheyi. Format:
   ```text
   mongodb+srv://<username>:<password>@cluster0.sfxte1d.mongodb.net/<dbname>?retryWrites=true&w=majority
   ```
4. **`<username>`** = na Atlas user (e.g. `team_10`)  
   **`<password>`** = na password (special chars unte URL-encode cheyi)  
   **`<dbname>`** = `ai-driver-drowsiness` (or na database name)

5. **Backend folder** lo `.env` open cheyi. Ee line exact ga update cheyi:

   ```env
   MONGO_URI=mongodb+srv://team_10:NA_PASSWORD@cluster0.sfxte1d.mongodb.net/ai-driver-drowsiness?retryWrites=true&w=majority
   ```

   `NA_PASSWORD` replace cheyi – special chars unte URL-encoded version use cheyi.

---

## Step 6: Backend restart cheyi

1. Terminal lo backend run chesina place lo **Ctrl+C** tho stop cheyi.
2. Again start cheyi:
   ```bash
   npm run dev
   ```
3. Message **"✅ MongoDB connected"** ravali.

---

## Still `querySrv ECONNREFUSED` unte

- **Wi‑Fi / network:** Different network try cheyi (e.g. mobile hotspot).  
  School/office network **DNS (port 53)** block chesthe SRV fail avuthundi.
- **Antivirus / firewall:** Temporarily off chesi try cheyi; MongoDB connection allow cheyani rule add cheyi.
- **Atlas status:** https://status.mongodb.com lo outages chudu.

---

## Quick checklist

| Step | Check |
|------|--------|
| 1 | Atlas lo login ayyava? |
| 2 | Network Access lo IP add / "Allow from Anywhere" chesava? |
| 3 | Cluster "Paused" kadu – Resume chesava? |
| 4 | Username & password `.env` lo correct ga unaya? (special chars → URL-encode) |
| 5 | `.env` save chesi backend restart chesava? |

Ivi chesaka kuda connect avakapothe, exact error message (full line) copy chesi pampu.

---

## IP add chesina kuda connection fail aithe

Ee points verify cheyi:

### 1. Correct project lo add chesava?
- Atlas lo **multiple projects** unte, **cluster0 (sfxte1d) unde same project** lo Network Access open cheyi.
- Top-left lo project name chudu → cluster **cluster0** e project lo undi ani confirm cheyi. **Adi project select chesi** left side **Network Access** open cheyi.

### 2. "Network Access" lo add chesava? (Database Access kadu)
- Left sidebar lo **"Network Access"** (Security section) — idhi correct.
- **"Database Access"** (users) kadu — adhi IP list kadu.

### 3. Entry status "Active" ga unda?
- Network Access list lo na entry **"Active"** (green) ga undali. **"Pending"** unte 2–3 min wait cheyi.

### 4. "Allow from Anywhere" try cheyi
- **"Add IP Address"** → **"Allow Access from Anywhere"** select cheyi → **Confirm**.
- Itho `0.0.0.0/0` add avuthundi. **"Add Current IP"** only add chesav ante, IP change ayyi undochu (Wi‑Fi/dynamic IP).

### 5. Password correct ga unda?
- **Database Access** → user **team10** → Edit → password **team10** (or .env lo unna password) set cheyi.
- .env lo: `MONGO_URI_STANDARD=mongodb://team10:TEAM10_PASSWORD@...` — password exact ga match avvali.

### 6. Backend restart + wait
- Terminal lo **Ctrl+C** → `npm run dev` — 15s retry add chesam, so 15–30 sec wait cheyi; "✅ MongoDB connected" ravali.
