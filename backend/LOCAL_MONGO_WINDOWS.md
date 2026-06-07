# Local MongoDB – Windows lo Install (Atlas avatledu ante)

Atlas connect avatledu ante **computer lo ne MongoDB install** chesi run cheyochu. App ippudu `.env` lo `MONGO_URI=mongodb://127.0.0.1:27017/ai-driver-drowsiness` use chestundi (local).

---

## Option A: MongoDB Installer (recommended)

1. **Download**
   - https://www.mongodb.com/try/download/community
   - Version: 7.x or 8.x, Windows x64, **msi** download.

2. **Install**
   - Run the **.msi**.
   - "Complete" install select cheyi.
   - **"Install MongoDB as a Service"** check cheyi (so auto start avuthundi).
   - Install finish ayyaka MongoDB **service** run avuthundi.

3. **Verify**
   - Open new terminal:
     ```bash
     mongosh
     ```
   - Or old version: `mongo`
   - Connection aithe `> ` prompt vasthundi. Type `exit` and press Enter.

4. **Backend**
   - `.env` lo already `MONGO_URI=mongodb://127.0.0.1:27017/ai-driver-drowsiness` set chesam.
   - Terminal lo: `npm run dev`
   - **"✅ MongoDB connected"** ravali.

---

## Option B: Docker (Docker Desktop unte)

```bash
docker run -d -p 27017:27017 --name mongo mongo:latest
```

Taruvata backend: `npm run dev` → **"✅ MongoDB connected"**.

---

## Service start cheyali ante (Option A)

- **Services** open cheyi (Win + R → `services.msc` → Enter).
- List lo **"MongoDB Server"** find cheyi → right-click → **Start**.
- Or CMD/PowerShell (Admin): `net start MongoDB`

---

## Summary

| Step | Action |
|------|--------|
| 1 | MongoDB Community download & install (Option A) or `docker run ...` (Option B) |
| 2 | `.env` lo `MONGO_URI=mongodb://127.0.0.1:27017/ai-driver-drowsiness` — already set |
| 3 | `npm run dev` — "✅ MongoDB connected" ravali |

Atlas avasaram ledu — local tho login/register full ga work avuthundi.
