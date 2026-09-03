// Installs the import-map hook. Used as `node --import ./register.mjs --test .`
import { register } from "node:module";
register("./import-map.mjs", import.meta.url);
