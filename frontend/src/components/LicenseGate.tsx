import React, { useState } from "react";
import { useAppStore, isValidLicenseFormat } from "../store/config";
import { validateLicense } from "../services/api";

/**
 * Pantalla de primer inicio que bloquea la app hasta que se introduzca
 * una clave de licencia beta válida.
 *
 * Estilo: editorial oscuro con acento magenta y textura sutil.
 */
export const LicenseGate: React.FC = () => {
  const { config, updateConfig } = useAppStore();
  const [keyInput, setKeyInput] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [validating, setValidating] = useState(false);

  // Si ya hay una clave guardada, no mostrar el gate
  // (el App.tsx ya hace este chequeo, pero por seguridad)
  if (config.licenseKey) return null;

  const handleActivate = async () => {
    const key = keyInput.trim().toUpperCase();
    if (!key) {
      setStatus("error|Introduce una clave de licencia");
      return;
    }
    if (!isValidLicenseFormat(key)) {
      setStatus("error|Formato inválido. Debe ser VNT-XXXX-XXXX-XXXX");
      return;
    }
    setValidating(true);
    setStatus("validating|Validando...");
    try {
      const result = await validateLicense(key);
      if (result.valid) {
        updateConfig({ licenseKey: key });
        setStatus("success|" + (result.message || "Licencia activada"));
      } else {
        setStatus("error|" + (result.message || "Clave inválida"));
      }
    } catch {
      setStatus("error|Error de conexión con el servidor");
    } finally {
      setValidating(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !validating) {
      handleActivate();
    }
  };

  const statusClass = status?.startsWith("error")
    ? "text-red-400"
    : status?.startsWith("success")
      ? "text-green-400"
      : "text-yellow-400";

  const statusText = status?.split("|")[1] ?? "";

  return (
    <div className="w-screen h-screen overflow-hidden bg-[#0a0a0a] flex flex-col items-center justify-center select-none relative">
      {/* Textura de fondo sutil */}
      <div className="absolute inset-0 opacity-[0.03] pointer-events-none"
        style={{
          backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M30 0v60M0 30h60' stroke='white' stroke-width='0.5'/%3E%3C/svg%3E")`,
          backgroundSize: "60px 60px",
        }}
      />

      {/* Destello de fondo degradado */}
      <div className="absolute -top-40 -right-40 w-96 h-96 rounded-full bg-[#8a2be2] opacity-[0.07] blur-3xl pointer-events-none" />
      <div className="absolute -bottom-40 -left-40 w-96 h-96 rounded-full bg-[#ff0066] opacity-[0.05] blur-3xl pointer-events-none" />

      <div className="flex flex-col items-center gap-8 z-10 px-6 max-w-md w-full">
        {/* Logo / Marca */}
        <div className="flex flex-col items-center gap-2">
          <div className="w-14 h-14 rounded-full border-2 border-[#8a2be2] flex items-center justify-center">
            <span className="text-[#8a2be2] text-2xl font-bold tracking-tight">V</span>
          </div>
        </div>

        {/* Título */}
        <div className="text-center">
          <h1 className="text-white text-2xl font-bold tracking-tight leading-tight">
            Vantare Ingeniero IA
          </h1>
          <p className="text-[#666] text-[13px] mt-2 tracking-wide uppercase font-medium">
            Beta — Licencia Requerida
          </p>
        </div>

        {/* Input de clave */}
        <div className="w-full flex flex-col gap-3">
          <label className="text-[10px] text-[#555] uppercase tracking-[0.15em] font-medium text-center">
            Introduce tu clave de licencia beta
          </label>
          <input
            type="text"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value.toUpperCase())}
            onKeyDown={handleKeyDown}
            placeholder="VNT-XXXX-XXXX-XXXX"
            disabled={validating}
            className="w-full bg-[#141414] border border-[#222] rounded-lg px-4 py-3 text-[14px] text-white
                       placeholder:text-[#444] placeholder:tracking-wider
                       focus:border-[#8a2be2] focus:outline-none focus:ring-1 focus:ring-[#8a2be2]/30
                       disabled:opacity-50 text-center tracking-[0.15em] font-mono"
            autoFocus
          />
          <p className="text-[9px] text-[#444] text-center tracking-wide">
            Formato: VNT + 12 caracteres alfanuméricos en grupos de 4
          </p>
        </div>

        {/* Botón */}
        <button
          onClick={handleActivate}
          disabled={validating}
          className={`w-full py-3 rounded-lg text-[12px] font-bold uppercase tracking-[0.2em] transition-all duration-200 ${
            validating
              ? "bg-[#222] text-[#555] cursor-not-allowed"
              : "bg-[#8a2be2] hover:bg-[#9d3ff3] text-white active:scale-[0.98] shadow-lg shadow-[#8a2be2]/20"
          }`}
        >
          {validating ? "Validando..." : "Activar"}
        </button>

        {/* Mensaje de estado */}
        {status && (
          <div className={`text-[12px] text-center font-medium ${statusClass}`}>
            {statusText}
          </div>
        )}

        {/* Footer */}
        <div className="mt-6 text-[9px] text-[#333] text-center tracking-wide uppercase">
          © {new Date().getFullYear()} Vantare Technologies
        </div>
      </div>
    </div>
  );
};

export default LicenseGate;
