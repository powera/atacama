import React, { useState, useEffect, useMemo } from 'react';
import {
  ArrowRightLeft,
  Maximize2,
  Minimize2,
  RefreshCcw,
  Thermometer,
  Ruler,
  Scale,
  Droplet,
} from 'lucide-react';
import { useFullscreen } from './useFullscreen';
import { useGlobalSettings } from './useGlobalSettings';

// Unit definitions and conversion factors relative to base units
const UNITS = {
  length: {
    label: 'Length',
    icon: Ruler,
    baseUnit: 'm',
    units: {
      m: { label: 'Meter (m)', toBase: (v) => v, fromBase: (v) => v },
      km: { label: 'Kilometer (km)', toBase: (v) => v * 1000, fromBase: (v) => v / 1000 },
      cm: { label: 'Centimeter (cm)', toBase: (v) => v * 0.01, fromBase: (v) => v / 0.01 },
      mm: { label: 'Millimeter (mm)', toBase: (v) => v * 0.001, fromBase: (v) => v / 0.001 },
      in: { label: 'Inch (in)', toBase: (v) => v * 0.0254, fromBase: (v) => v / 0.0254 },
      ft: { label: 'Foot (ft)', toBase: (v) => v * 0.3048, fromBase: (v) => v / 0.3048 },
      yd: { label: 'Yard (yd)', toBase: (v) => v * 0.9144, fromBase: (v) => v / 0.9144 },
      mi: { label: 'Mile (mi)', toBase: (v) => v * 1609.344, fromBase: (v) => v / 1609.344 },
    },
  },
  weight: {
    label: 'Weight',
    icon: Scale,
    baseUnit: 'kg',
    units: {
      kg: { label: 'Kilogram (kg)', toBase: (v) => v, fromBase: (v) => v },
      g: { label: 'Gram (g)', toBase: (v) => v * 0.001, fromBase: (v) => v / 0.001 },
      mg: { label: 'Milligram (mg)', toBase: (v) => v * 0.000001, fromBase: (v) => v / 0.000001 },
      lb: { label: 'Pound (lb)', toBase: (v) => v * 0.45359237, fromBase: (v) => v / 0.45359237 },
      oz: { label: 'Ounce (oz)', toBase: (v) => v * 0.0283495231, fromBase: (v) => v / 0.0283495231 },
      t: { label: 'Metric Ton (t)', toBase: (v) => v * 1000, fromBase: (v) => v / 1000 },
    },
  },
  temperature: {
    label: 'Temperature',
    icon: Thermometer,
    baseUnit: 'c',
    units: {
      c: {
        label: 'Celsius (°C)',
        toBase: (v) => v,
        fromBase: (v) => v,
      },
      f: {
        label: 'Fahrenheit (°F)',
        toBase: (v) => ((v - 32) * 5) / 9,
        fromBase: (v) => (v * 9) / 5 + 32,
      },
      k: {
        label: 'Kelvin (K)',
        toBase: (v) => v - 273.15,
        fromBase: (v) => v + 273.15,
      },
      r: {
        label: 'Rankine (°R)',
        toBase: (v) => (v - 491.67) * (5 / 9),
        fromBase: (v) => (v + 273.15) * (9 / 5),
      },
    },
  },
  volume: {
    label: 'Volume',
    icon: Droplet,
    baseUnit: 'l',
    units: {
      l: { label: 'Liter (L)', toBase: (v) => v, fromBase: (v) => v },
      ml: { label: 'Milliliter (mL)', toBase: (v) => v * 0.001, fromBase: (v) => v / 0.001 },
      m3: { label: 'Cubic Meter (m³)', toBase: (v) => v * 1000, fromBase: (v) => v / 1000 },
      tsp: { label: 'Teaspoon (tsp)', toBase: (v) => v * 0.00492892, fromBase: (v) => v / 0.00492892 },
      tbsp: { label: 'Tablespoon (tbsp)', toBase: (v) => v * 0.0147868, fromBase: (v) => v / 0.0147868 },
      fl_oz: { label: 'Fluid Ounce (fl oz)', toBase: (v) => v * 0.0295735, fromBase: (v) => v / 0.0295735 },
      cup: { label: 'Cup (US)', toBase: (v) => v * 0.24, fromBase: (v) => v / 0.24 },
      pt: { label: 'Pint (US)', toBase: (v) => v * 0.473176, fromBase: (v) => v / 0.473176 },
      qt: { label: 'Quart (US)', toBase: (v) => v * 0.946353, fromBase: (v) => v / 0.946353 },
      gal: { label: 'Gallon (US)', toBase: (v) => v * 3.78541, fromBase: (v) => v / 3.78541 },
    },
  },
};

const UnitConverter = () => {
  // Fullscreen hook for toggling fullscreen mode
  const { isFullscreen, toggleFullscreen, containerRef } = useFullscreen();

  // Global settings hook (not used here but included for extensibility)
  const { SettingsToggle, SettingsModal } = useGlobalSettings();

  // State: selected measurement category
  const [category, setCategory] = useState('length');

  // State: input value as string to allow partial input and validation
  const [inputValue, setInputValue] = useState('');

  // State: selected input unit and output unit
  const [inputUnit, setInputUnit] = useState(() => {
    const units = Object.keys(UNITS[category].units);
    return units[0];
  });
  const [outputUnit, setOutputUnit] = useState(() => {
    const units = Object.keys(UNITS[category].units);
    return units[1] || units[0];
  });

  // State: error message for invalid input
  const [error, setError] = useState(null);

  // When category changes, reset units and input
  useEffect(() => {
    const units = Object.keys(UNITS[category].units);
    setInputUnit(units[0]);
    setOutputUnit(units[1] || units[0]);
    setInputValue('');
    setError(null);
  }, [category]);

  // Parse input value safely to number or null
  const parsedInput = useMemo(() => {
    if (inputValue.trim() === '') return null;
    // Accept numbers with optional decimal and optional leading +/-
    const num = Number(inputValue);
    if (isNaN(num)) return null;
    return num;
  }, [inputValue]);

  // Conversion logic
  const convertedValue = useMemo(() => {
    if (parsedInput === null) return '';
    try {
      const cat = UNITS[category];
      const fromUnit = cat.units[inputUnit];
      const toUnit = cat.units[outputUnit];

      // Convert input to base unit
      const baseValue = fromUnit.toBase(parsedInput);

      // Special handling for temperature: no linear scale for negative Kelvin, etc.
      // Already handled in conversion functions

      // Convert base unit to output unit
      const outValue = toUnit.fromBase(baseValue);

      // Format output with reasonable precision
      if (category === 'temperature') {
        // Temperature: 2 decimals max
        return outValue.toFixed(2);
      } else if (category === 'length' || category === 'weight' || category === 'volume') {
        // Length, weight, volume: 4 decimals max, trim trailing zeros
        return parseFloat(outValue.toFixed(4)).toString();
      }
      return outValue.toString();
    } catch {
      return '';
    }
  }, [parsedInput, category, inputUnit, outputUnit]);

  // Handle input change with validation
  const onInputChange = (e) => {
    const val = e.target.value;
    // Allow empty, numbers, decimal point, +/-, and scientific notation e.g. 1e3
    if (
      val === '' ||
      /^[-+]?(\d+(\.\d*)?|\.\d+)(e[-+]?\d+)?$/i.test(val.trim())
    ) {
      setInputValue(val);
      setError(null);
    } else {
      setError('Invalid number format');
      setInputValue(val);
    }
  };

  // Swap units and values
  const onSwap = () => {
    setInputUnit(outputUnit);
    setOutputUnit(inputUnit);
    setInputValue(convertedValue);
    setError(null);
  };

  // Reset all to defaults
  const onReset = () => {
    const units = Object.keys(UNITS[category].units);
    setInputUnit(units[0]);
    setOutputUnit(units[1] || units[0]);
    setInputValue('');
    setError(null);
  };

  // Icons for categories
  const CategoryIcon = UNITS[category].icon;

  return (
    <div
      ref={containerRef}
      className={isFullscreen ? 'w-fullscreen' : 'w-container'}
      role="main"
      aria-label="Unit Converter Widget"
      tabIndex={-1}
    >
      <header className="widget-header" style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
        <h1 style={{ flex: '1 1 auto', minWidth: 200 }}>
          <CategoryIcon style={{ verticalAlign: 'middle', marginRight: 8 }} aria-hidden="true" />
          Unit Converter
        </h1>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <SettingsToggle aria-label="Open settings" />
          <button
            type="button"
            onClick={toggleFullscreen}
            className="w-button"
            aria-pressed={isFullscreen}
            aria-label={isFullscreen ? 'Exit fullscreen mode' : 'Enter fullscreen mode'}
            title={isFullscreen ? 'Exit fullscreen' : 'Fullscreen'}
            style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}
          >
            {isFullscreen ? <Minimize2 size={18} /> : <Maximize2 size={18} />}
            <span className="w-hide-mobile" style={{ userSelect: 'none' }}>
              {isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
            </span>
          </button>
        </div>
      </header>

      {/* Category selector */}
      <section aria-label="Select measurement category" className="w-mode-selector" style={{ justifyContent: 'center' }}>
        {Object.entries(UNITS).map(([key, { label, icon: Icon }]) => (
          <button
            key={key}
            type="button"
            className={`w-mode-option ${category === key ? 'w-active' : ''}`}
            onClick={() => setCategory(key)}
            aria-pressed={category === key}
            aria-label={`Select ${label} category`}
            title={label}
          >
            <Icon size={16} style={{ verticalAlign: 'middle', marginRight: 6 }} aria-hidden="true" />
            {label}
          </button>
        ))}
      </section>

      {/* Converter form */}
      <form
        onSubmit={(e) => e.preventDefault()}
        aria-live="polite"
        aria-relevant="additions removals"
        style={{ maxWidth: 600, margin: '0 auto' }}
      >
        <div className="form-group">
          <label htmlFor="inputValue">Enter value to convert</label>
          <input
            id="inputValue"
            name="inputValue"
            type="text"
            inputMode="decimal"
            autoComplete="off"
            placeholder="Enter number"
            value={inputValue}
            onChange={onInputChange}
            aria-describedby="inputError"
            aria-invalid={!!error}
          />
          {error && (
            <small id="inputError" className="error" role="alert" style={{ marginTop: '0.25rem' }}>
              {error}
            </small>
          )}
        </div>

        <div className="form-group" style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 45%' }}>
            <label htmlFor="inputUnit">From unit</label>
            <select
              id="inputUnit"
              name="inputUnit"
              value={inputUnit}
              onChange={(e) => setInputUnit(e.target.value)}
              aria-label="Select input unit"
            >
              {Object.entries(UNITS[category].units).map(([key, { label }]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          <div
            style={{
              alignSelf: 'flex-end',
              display: 'flex',
              justifyContent: 'center',
              flex: '0 0 40px',
              marginTop: 28,
            }}
          >
            <button
              type="button"
              onClick={onSwap}
              aria-label="Swap input and output units"
              title="Swap units"
              className="w-button-secondary"
              style={{ padding: '0.5rem', minWidth: 40, display: 'flex', justifyContent: 'center', alignItems: 'center' }}
            >
              <ArrowRightLeft size={20} />
            </button>
          </div>

          <div style={{ flex: '1 1 45%' }}>
            <label htmlFor="outputUnit">To unit</label>
            <select
              id="outputUnit"
              name="outputUnit"
              value={outputUnit}
              onChange={(e) => setOutputUnit(e.target.value)}
              aria-label="Select output unit"
            >
              {Object.entries(UNITS[category].units).map(([key, { label }]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div
          aria-live="polite"
          aria-atomic="true"
          className="w-feedback"
          style={{
            marginTop: '1.5rem',
            fontSize: '1.25rem',
            fontWeight: '600',
            color: error ? 'var(--color-error)' : 'var(--color-primary)',
            backgroundColor: error ? 'rgba(255,0,0,0.1)' : 'rgba(0,116,217,0.1)',
            borderRadius: 'var(--border-radius)',
            padding: 'var(--spacing-base)',
            minHeight: 44,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
          role="region"
        >
          {inputValue.trim() === '' ? (
            <span>Enter a value and select units to convert.</span>
          ) : error ? (
            <span>{error}</span>
          ) : convertedValue === '' ? (
            <span>Conversion not available.</span>
          ) : (
            <>
              <span>
                {inputValue} {UNITS[category].units[inputUnit].label} ={' '}
                <strong>
                  {convertedValue} {UNITS[category].units[outputUnit].label}
                </strong>
              </span>
            </>
          )}
        </div>

        <div
          style={{
            marginTop: '2rem',
            display: 'flex',
            justifyContent: 'center',
            gap: '1rem',
            flexWrap: 'wrap',
          }}
        >
          <button
            type="button"
            onClick={onReset}
            className="w-button-secondary"
            aria-label="Reset converter"
          >
            <RefreshCcw size={16} style={{ marginRight: 6 }} />
            Reset
          </button>
        </div>
      </form>

      <SettingsModal />
    </div>
  );
};

export default UnitConverter;
