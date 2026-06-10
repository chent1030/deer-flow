"use client";

import { useState } from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

type CronTab = "minute" | "hour" | "day" | "month" | "week";

const WEEK_OPTIONS = [
  { value: "1", label: "周一" },
  { value: "2", label: "周二" },
  { value: "3", label: "周三" },
  { value: "4", label: "周四" },
  { value: "5", label: "周五" },
  { value: "6", label: "周六" },
  { value: "0", label: "周日" },
];

interface CronFieldConfig {
  label: string;
  min: number;
  max: number;
}

const FIELD_CONFIG: Record<string, CronFieldConfig> & {
  minute: CronFieldConfig;
  hour: CronFieldConfig;
  day: CronFieldConfig;
  month: CronFieldConfig;
} = {
  minute: { label: "分钟", min: 0, max: 59 },
  hour: { label: "小时", min: 0, max: 23 },
  day: { label: "日", min: 1, max: 31 },
  month: { label: "月", min: 1, max: 12 },
};

interface CronBuilderProps {
  value: string;
  onChange: (value: string) => void;
}

interface FieldState {
  type: "every" | "range" | "step" | "specify";
  rangeStart: number;
  rangeEnd: number;
  stepStart: number;
  stepStep: number;
  specifyValues: number[];
}

function parseField(field: string, config: CronFieldConfig): FieldState {
  const state: FieldState = {
    type: "every",
    rangeStart: config.min,
    rangeEnd: config.max,
    stepStart: config.min,
    stepStep: 1,
    specifyValues: [],
  };

  if (field === "*") return state;

  if (field.includes("/")) {
    const parts = field.split("/");
    const startStr = parts[0] ?? "*";
    const stepStr = parts[1] ?? "1";
    state.type = "step";
    state.stepStart = startStr === "*" ? config.min : parseInt(startStr, 10);
    state.stepStep = parseInt(stepStr, 10);
  } else if (field.includes("-")) {
    const parts = field.split("-");
    state.type = "range";
    state.rangeStart = parseInt(parts[0] ?? String(config.min), 10);
    state.rangeEnd = parseInt(parts[1] ?? String(config.max), 10);
  } else if (field.includes(",")) {
    state.type = "specify";
    state.specifyValues = field.split(",").map((v) => parseInt(v, 10));
  } else {
    state.type = "specify";
    state.specifyValues = [parseInt(field, 10)];
  }

  return state;
}

function parseWeekField(field: string): FieldState {
  const state: FieldState = {
    type: "every",
    rangeStart: 0,
    rangeEnd: 6,
    stepStart: 0,
    stepStep: 1,
    specifyValues: [],
  };

  if (field === "*") return state;

  if (field.includes(",")) {
    state.type = "specify";
    state.specifyValues = field.split(",").map((v) => parseInt(v, 10));
  } else if (field.includes("-")) {
    const parts = field.split("-");
    state.type = "range";
    state.rangeStart = parseInt(parts[0] ?? "0", 10);
    state.rangeEnd = parseInt(parts[1] ?? "6", 10);
  } else {
    state.type = "specify";
    state.specifyValues = [parseInt(field, 10)];
  }

  return state;
}

function fieldToString(state: FieldState): string {
  switch (state.type) {
    case "every":
      return "*";
    case "range":
      return `${state.rangeStart}-${state.rangeEnd}`;
    case "step":
      return `${state.stepStart}/${state.stepStep}`;
    case "specify":
      return state.specifyValues.length > 0 ? state.specifyValues.sort((a, b) => a - b).join(",") : "*";
  }
}

function parseCron(expr: string): { fields: string[]; activeTab: CronTab } {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return { fields: ["*", "*", "*", "*", "*"], activeTab: "minute" };

  const minute = parts[0] ?? "*";
  const hour = parts[1] ?? "*";
  const day = parts[2] ?? "*";
  const month = parts[3] ?? "*";
  const week = parts[4] ?? "*";

  if (week !== "*") return { fields: [minute, hour, day, month, week], activeTab: "week" };
  if (month !== "*") return { fields: [minute, hour, day, month, week], activeTab: "month" };
  if (day !== "*") return { fields: [minute, hour, day, month, week], activeTab: "day" };
  if (hour !== "*") return { fields: [minute, hour, day, month, week], activeTab: "hour" };
  return { fields: [minute, hour, day, month, week], activeTab: "minute" };
}

function cronToHuman(expr: string): string {
  const parts = expr.trim().split(/\s+/);
  if (parts.length !== 5) return expr;

  const minute = parts[0] ?? "*";
  const hour = parts[1] ?? "*";
  const day = parts[2] ?? "*";
  const month = parts[3] ?? "*";
  const week = parts[4] ?? "*";

  if (minute === "*" && hour === "*" && day === "*" && month === "*" && week === "*") {
    return "每分钟";
  }

  if (hour === "*" && day === "*" && month === "*" && week === "*") {
    if (minute.includes("/")) {
      const step = minute.split("/")[1];
      return `每 ${step} 分钟`;
    }
    return `每小时的第 ${minute} 分`;
  }

  if (day === "*" && month === "*" && week === "*") {
    return `每天 ${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`;
  }

  if (month === "*" && week === "*") {
    return `每月 ${day}号 ${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`;
  }

  if (day === "*" && month === "*") {
    const dayLabel = WEEK_OPTIONS.find((o) => o.value === week)?.label ?? `周${week}`;
    if (week.includes(",")) {
      const labels = week.split(",").map((w) => WEEK_OPTIONS.find((o) => o.value === w)?.label ?? w);
      return `每 ${labels.join("、")} ${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`;
    }
    return `每${dayLabel} ${hour.padStart(2, "0")}:${minute.padStart(2, "0")}`;
  }

  return expr;
}

function NumberGrid({
  min,
  max,
  selected,
  onToggle,
  cols = 10,
}: {
  min: number;
  max: number;
  selected: number[];
  onToggle: (val: number) => void;
  cols?: number;
}) {
  const numbers = Array.from({ length: max - min + 1 }, (_, i) => min + i);
  return (
    <div className="grid gap-1" style={{ gridTemplateColumns: `repeat(${cols}, 1fr)` }}>
      {numbers.map((n) => {
        const isSelected = selected.includes(n);
        return (
          <button
            key={n}
            type="button"
            onClick={() => onToggle(n)}
            className={`rounded px-1 py-0.5 text-xs transition-colors ${
              isSelected
                ? "bg-primary text-primary-foreground"
                : "bg-muted hover:bg-muted/80"
            }`}
          >
            {n}
          </button>
        );
      })}
    </div>
  );
}

function FieldEditor({
  state,
  onChange,
  config,
}: {
  state: FieldState;
  onChange: (state: FieldState) => void;
  config: CronFieldConfig;
}) {
  return (
    <div className="flex flex-col gap-3">
      <RadioGroup
        value={state.type}
        onValueChange={(v) =>
          onChange({ ...state, type: v as FieldState["type"] })
        }
      >
        <div className="flex items-center gap-2">
          <RadioGroupItem value="every" id={`every-${config.label}`} />
          <Label htmlFor={`every-${config.label}`}>
            每{config.label}（*）
          </Label>
        </div>
        <div className="flex items-center gap-2">
          <RadioGroupItem value="range" id={`range-${config.label}`} />
          <Label htmlFor={`range-${config.label}`} className="flex items-center gap-1">
            从
            <Input
              type="number"
              min={config.min}
              max={config.max}
              value={state.rangeStart}
              onChange={(e) =>
                onChange({ ...state, rangeStart: parseInt(e.target.value, 10) || config.min })
              }
              className="mx-1 w-16"
              disabled={state.type !== "range"}
            />
            到
            <Input
              type="number"
              min={config.min}
              max={config.max}
              value={state.rangeEnd}
              onChange={(e) =>
                onChange({ ...state, rangeEnd: parseInt(e.target.value, 10) || config.max })
              }
              className="mx-1 w-16"
              disabled={state.type !== "range"}
            />
            {config.label}，每{config.label}执行一次
          </Label>
        </div>
        <div className="flex items-center gap-2">
          <RadioGroupItem value="step" id={`step-${config.label}`} />
          <Label htmlFor={`step-${config.label}`} className="flex items-center gap-1">
            从
            <Input
              type="number"
              min={config.min}
              max={config.max}
              value={state.stepStart}
              onChange={(e) =>
                onChange({ ...state, stepStart: parseInt(e.target.value, 10) || config.min })
              }
              className="mx-1 w-16"
              disabled={state.type !== "step"}
            />
            开始，每
            <Input
              type="number"
              min={1}
              max={config.max - config.min + 1}
              value={state.stepStep}
              onChange={(e) =>
                onChange({ ...state, stepStep: parseInt(e.target.value, 10) || 1 })
              }
              className="mx-1 w-16"
              disabled={state.type !== "step"}
            />
            {config.label}执行一次
          </Label>
        </div>
        <div className="flex items-start gap-2">
          <RadioGroupItem value="specify" id={`specify-${config.label}`} className="mt-1" />
          <Label htmlFor={`specify-${config.label}`} className="flex flex-col gap-2">
            指定（可多选）
            <NumberGrid
              min={config.min}
              max={config.max}
              selected={state.specifyValues}
              onToggle={(val) => {
                const next = state.specifyValues.includes(val)
                  ? state.specifyValues.filter((v) => v !== val)
                  : [...state.specifyValues, val];
                onChange({ ...state, type: "specify", specifyValues: next });
              }}
            />
          </Label>
        </div>
      </RadioGroup>
    </div>
  );
}

function WeekFieldEditor({
  state,
  onChange,
}: {
  state: FieldState;
  onChange: (state: FieldState) => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      <RadioGroup
        value={state.type}
        onValueChange={(v) =>
          onChange({ ...state, type: v as FieldState["type"] })
        }
      >
        <div className="flex items-center gap-2">
          <RadioGroupItem value="every" id="week-every" />
          <Label htmlFor="week-every">每周（*）</Label>
        </div>
        <div className="flex items-start gap-2">
          <RadioGroupItem value="specify" id="week-specify" className="mt-1" />
          <Label htmlFor="week-specify" className="flex flex-col gap-2">
            指定星期（可多选）
            <div className="flex flex-wrap gap-1">
              {WEEK_OPTIONS.map((opt) => {
                const val = parseInt(opt.value, 10);
                const isSelected = state.specifyValues.includes(val);
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => {
                      const next = isSelected
                        ? state.specifyValues.filter((v) => v !== val)
                        : [...state.specifyValues, val];
                      onChange({ ...state, type: "specify", specifyValues: next });
                    }}
                    className={`rounded px-3 py-1 text-xs transition-colors ${
                      isSelected
                        ? "bg-primary text-primary-foreground"
                        : "bg-muted hover:bg-muted/80"
                    }`}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </Label>
        </div>
      </RadioGroup>
    </div>
  );
}

export function CronBuilder({ value, onChange }: CronBuilderProps) {
  const { fields, activeTab } = parseCron(value);
  const [tab, setTab] = useState<CronTab>(activeTab);

  const [minuteState, setMinuteState] = useState(() => parseField(fields[0]!, FIELD_CONFIG.minute));
  const [hourState, setHourState] = useState(() => parseField(fields[1]!, FIELD_CONFIG.hour));
  const [dayState, setDayState] = useState(() => parseField(fields[2]!, FIELD_CONFIG.day));
  const [monthState, setMonthState] = useState(() => parseField(fields[3]!, FIELD_CONFIG.month));
  const [weekState, setWeekState] = useState(() => parseWeekField(fields[4]!));

  const emitChange = (
    newMinute: FieldState,
    newHour: FieldState,
    newDay: FieldState,
    newMonth: FieldState,
    newWeek: FieldState,
  ) => {
    const m = fieldToString(newMinute);
    const h = fieldToString(newHour);
    const d = fieldToString(newDay);
    const mo = fieldToString(newMonth);
    const w = fieldToString(newWeek);
    onChange(`${m} ${h} ${d} ${mo} ${w}`);
  };

  const wrapHandler = (
    setter: React.Dispatch<React.SetStateAction<FieldState>>,
    fieldSetter: "minute" | "hour" | "day" | "month" | "week",
  ) => {
    return (newState: FieldState) => {
      setter(newState);
      const m = fieldSetter === "minute" ? newState : minuteState;
      const h = fieldSetter === "hour" ? newState : hourState;
      const d = fieldSetter === "day" ? newState : dayState;
      const mo = fieldSetter === "month" ? newState : monthState;
      const w = fieldSetter === "week" ? newState : weekState;
      emitChange(m, h, d, mo, w);
    };
  };

  return (
    <div className="flex flex-col gap-3">
      <Tabs value={tab} onValueChange={(v) => setTab(v as CronTab)}>
        <TabsList className="w-full">
          <TabsTrigger value="minute" className="flex-1">分</TabsTrigger>
          <TabsTrigger value="hour" className="flex-1">时</TabsTrigger>
          <TabsTrigger value="day" className="flex-1">日</TabsTrigger>
          <TabsTrigger value="month" className="flex-1">月</TabsTrigger>
          <TabsTrigger value="week" className="flex-1">周</TabsTrigger>
        </TabsList>

        <TabsContent value="minute" className="mt-3">
          <FieldEditor
            state={minuteState}
            onChange={wrapHandler(setMinuteState, "minute")}
            config={FIELD_CONFIG.minute}
          />
        </TabsContent>

        <TabsContent value="hour" className="mt-3">
          <FieldEditor
            state={hourState}
            onChange={wrapHandler(setHourState, "hour")}
            config={FIELD_CONFIG.hour}
          />
        </TabsContent>

        <TabsContent value="day" className="mt-3">
          <FieldEditor
            state={dayState}
            onChange={wrapHandler(setDayState, "day")}
            config={FIELD_CONFIG.day}
          />
        </TabsContent>

        <TabsContent value="month" className="mt-3">
          <FieldEditor
            state={monthState}
            onChange={wrapHandler(setMonthState, "month")}
            config={FIELD_CONFIG.month}
          />
        </TabsContent>

        <TabsContent value="week" className="mt-3">
          <WeekFieldEditor
            state={weekState}
            onChange={wrapHandler(setWeekState, "week")}
          />
        </TabsContent>
      </Tabs>

      <div className="bg-muted/50 rounded-md p-3 text-sm">
        <span className="text-muted-foreground">表达式：</span>
        <code className="font-mono">{value}</code>
        <span className="text-muted-foreground ml-3">释义：</span>
        <span>{cronToHuman(value)}</span>
      </div>
    </div>
  );
}

export { cronToHuman };
