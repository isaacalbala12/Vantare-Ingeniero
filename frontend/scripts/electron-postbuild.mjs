import { writeFileSync } from "node:fs";

writeFileSync("electron-dist/package.json", JSON.stringify({ type: "commonjs" }, null, 2));
