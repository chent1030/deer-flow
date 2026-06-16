"use client";

import { useEffect, useRef, useState } from "react";

interface AnimatedLoginCharactersProps {
  isTyping: boolean;
  passwordLength: number;
  showPassword: boolean;
}

interface PupilProps {
  size?: number;
  maxDistance?: number;
  color?: string;
  forceLookX?: number;
  forceLookY?: number;
}

interface EyeBallProps extends PupilProps {
  eyeSize?: number;
  pupilSize?: number;
  eyeColor?: string;
  blinking?: boolean;
}

function usePointerPosition() {
  const [position, setPosition] = useState({ x: 0, y: 0 });

  useEffect(() => {
    const handlePointerMove = (event: PointerEvent) => {
      setPosition({ x: event.clientX, y: event.clientY });
    };

    window.addEventListener("pointermove", handlePointerMove);
    return () => window.removeEventListener("pointermove", handlePointerMove);
  }, []);

  return position;
}

function useBlinking() {
  const [blinking, setBlinking] = useState(false);

  useEffect(() => {
    let blinkTimer: ReturnType<typeof setTimeout> | undefined;
    let resetTimer: ReturnType<typeof setTimeout> | undefined;

    const scheduleBlink = () => {
      blinkTimer = setTimeout(
        () => {
          setBlinking(true);
          resetTimer = setTimeout(() => {
            setBlinking(false);
            scheduleBlink();
          }, 140);
        },
        Math.random() * 3600 + 2800,
      );
    };

    scheduleBlink();

    return () => {
      if (blinkTimer) clearTimeout(blinkTimer);
      if (resetTimer) clearTimeout(resetTimer);
    };
  }, []);

  return blinking;
}

function getTrackedOffset(
  element: HTMLElement | null,
  pointerX: number,
  pointerY: number,
  maxDistance: number,
) {
  if (!element) return { x: 0, y: 0 };

  const rect = element.getBoundingClientRect();
  const centerX = rect.left + rect.width / 2;
  const centerY = rect.top + rect.height / 2;
  const deltaX = pointerX - centerX;
  const deltaY = pointerY - centerY;
  const distance = Math.min(Math.hypot(deltaX, deltaY), maxDistance);
  const angle = Math.atan2(deltaY, deltaX);

  return {
    x: Math.cos(angle) * distance,
    y: Math.sin(angle) * distance,
  };
}

function Pupil({
  size = 12,
  maxDistance = 5,
  color = "#2D2D2D",
  forceLookX,
  forceLookY,
}: PupilProps) {
  const ref = useRef<HTMLDivElement>(null);
  const pointer = usePointerPosition();
  const offset =
    forceLookX !== undefined && forceLookY !== undefined
      ? { x: forceLookX, y: forceLookY }
      : getTrackedOffset(ref.current, pointer.x, pointer.y, maxDistance);

  return (
    <div
      ref={ref}
      className="rounded-full transition-transform duration-100 ease-out"
      style={{
        width: size,
        height: size,
        backgroundColor: color,
        transform: `translate(${offset.x}px, ${offset.y}px)`,
      }}
    />
  );
}

function EyeBall({
  eyeSize = 18,
  pupilSize = 7,
  maxDistance = 5,
  eyeColor = "white",
  color = "#2D2D2D",
  blinking = false,
  forceLookX,
  forceLookY,
}: EyeBallProps) {
  const ref = useRef<HTMLDivElement>(null);
  const pointer = usePointerPosition();
  const offset =
    forceLookX !== undefined && forceLookY !== undefined
      ? { x: forceLookX, y: forceLookY }
      : getTrackedOffset(ref.current, pointer.x, pointer.y, maxDistance);

  return (
    <div
      ref={ref}
      className="flex items-center justify-center overflow-hidden rounded-full transition-all duration-150"
      style={{
        width: eyeSize,
        height: blinking ? 2 : eyeSize,
        backgroundColor: eyeColor,
      }}
    >
      {!blinking && (
        <div
          className="rounded-full transition-transform duration-100 ease-out"
          style={{
            width: pupilSize,
            height: pupilSize,
            backgroundColor: color,
            transform: `translate(${offset.x}px, ${offset.y}px)`,
          }}
        />
      )}
    </div>
  );
}

function getCharacterPose(
  element: HTMLElement | null,
  pointerX: number,
  pointerY: number,
) {
  if (!element) return { faceX: 0, faceY: 0, bodySkew: 0 };

  const rect = element.getBoundingClientRect();
  const centerX = rect.left + rect.width / 2;
  const centerY = rect.top + rect.height / 3;
  const deltaX = pointerX - centerX;
  const deltaY = pointerY - centerY;

  return {
    faceX: Math.max(-15, Math.min(15, deltaX / 20)),
    faceY: Math.max(-10, Math.min(10, deltaY / 30)),
    bodySkew: Math.max(-6, Math.min(6, -deltaX / 120)),
  };
}

export function AnimatedLoginCharacters({
  isTyping,
  passwordLength,
  showPassword,
}: AnimatedLoginCharactersProps) {
  const pointer = usePointerPosition();
  const purpleRef = useRef<HTMLDivElement>(null);
  const blackRef = useRef<HTMLDivElement>(null);
  const orangeRef = useRef<HTMLDivElement>(null);
  const yellowRef = useRef<HTMLDivElement>(null);
  const purpleBlinking = useBlinking();
  const blackBlinking = useBlinking();
  const [lookAtEachOther, setLookAtEachOther] = useState(false);
  const [purplePeeking, setPurplePeeking] = useState(false);

  const hasPassword = passwordLength > 0;
  const passwordVisible = hasPassword && showPassword;
  const passwordHidden = hasPassword && !showPassword;

  useEffect(() => {
    if (!isTyping) {
      setLookAtEachOther(false);
      return;
    }

    setLookAtEachOther(true);
    const timer = setTimeout(() => setLookAtEachOther(false), 800);
    return () => clearTimeout(timer);
  }, [isTyping]);

  useEffect(() => {
    if (!passwordVisible) {
      setPurplePeeking(false);
      return;
    }

    const timer = setTimeout(
      () => {
        setPurplePeeking(true);
        setTimeout(() => setPurplePeeking(false), 700);
      },
      Math.random() * 2600 + 1800,
    );

    return () => clearTimeout(timer);
  }, [passwordVisible, purplePeeking]);

  const purple = getCharacterPose(purpleRef.current, pointer.x, pointer.y);
  const black = getCharacterPose(blackRef.current, pointer.x, pointer.y);
  const orange = getCharacterPose(orangeRef.current, pointer.x, pointer.y);
  const yellow = getCharacterPose(yellowRef.current, pointer.x, pointer.y);

  return (
    <div
      aria-hidden="true"
      className="relative h-[400px] w-[550px] max-w-full"
    >
      <div
        ref={purpleRef}
        className="absolute bottom-0 transition-all duration-700 ease-in-out"
        style={{
          left: 70,
          width: 180,
          height: isTyping || passwordHidden ? 440 : 400,
          backgroundColor: "#6C3FF5",
          borderRadius: "10px 10px 0 0",
          zIndex: 1,
          transform: passwordVisible
            ? "skewX(0deg)"
            : isTyping || passwordHidden
              ? `skewX(${purple.bodySkew - 12}deg) translateX(40px)`
              : `skewX(${purple.bodySkew}deg)`,
          transformOrigin: "bottom center",
        }}
      >
        <div
          className="absolute flex gap-8 transition-all duration-700 ease-in-out"
          style={{
            left: passwordVisible
              ? 20
              : lookAtEachOther
                ? 55
                : 45 + purple.faceX,
            top: passwordVisible
              ? 35
              : lookAtEachOther
                ? 65
                : 40 + purple.faceY,
          }}
        >
          <EyeBall
            blinking={purpleBlinking}
            forceLookX={
              passwordVisible
                ? purplePeeking
                  ? 4
                  : -4
                : lookAtEachOther
                  ? 3
                  : undefined
            }
            forceLookY={
              passwordVisible
                ? purplePeeking
                  ? 5
                  : -4
                : lookAtEachOther
                  ? 4
                  : undefined
            }
          />
          <EyeBall
            blinking={purpleBlinking}
            forceLookX={
              passwordVisible
                ? purplePeeking
                  ? 4
                  : -4
                : lookAtEachOther
                  ? 3
                  : undefined
            }
            forceLookY={
              passwordVisible
                ? purplePeeking
                  ? 5
                  : -4
                : lookAtEachOther
                  ? 4
                  : undefined
            }
          />
        </div>
      </div>

      <div
        ref={blackRef}
        className="absolute bottom-0 transition-all duration-700 ease-in-out"
        style={{
          left: 240,
          width: 120,
          height: 310,
          backgroundColor: "#2D2D2D",
          borderRadius: "8px 8px 0 0",
          zIndex: 2,
          transform: passwordVisible
            ? "skewX(0deg)"
            : lookAtEachOther
              ? `skewX(${black.bodySkew * 1.5 + 10}deg) translateX(20px)`
              : isTyping || passwordHidden
                ? `skewX(${black.bodySkew * 1.5}deg)`
                : `skewX(${black.bodySkew}deg)`,
          transformOrigin: "bottom center",
        }}
      >
        <div
          className="absolute flex gap-6 transition-all duration-700 ease-in-out"
          style={{
            left: passwordVisible
              ? 10
              : lookAtEachOther
                ? 32
                : 26 + black.faceX,
            top: passwordVisible
              ? 28
              : lookAtEachOther
                ? 12
                : 32 + black.faceY,
          }}
        >
          <EyeBall
            eyeSize={16}
            pupilSize={6}
            maxDistance={4}
            blinking={blackBlinking}
            forceLookX={passwordVisible ? -4 : lookAtEachOther ? 0 : undefined}
            forceLookY={passwordVisible ? -4 : lookAtEachOther ? -4 : undefined}
          />
          <EyeBall
            eyeSize={16}
            pupilSize={6}
            maxDistance={4}
            blinking={blackBlinking}
            forceLookX={passwordVisible ? -4 : lookAtEachOther ? 0 : undefined}
            forceLookY={passwordVisible ? -4 : lookAtEachOther ? -4 : undefined}
          />
        </div>
      </div>

      <div
        ref={orangeRef}
        className="absolute bottom-0 transition-all duration-700 ease-in-out"
        style={{
          left: 0,
          width: 240,
          height: 200,
          zIndex: 3,
          backgroundColor: "#FF9B6B",
          borderRadius: "120px 120px 0 0",
          transform: passwordVisible
            ? "skewX(0deg)"
            : `skewX(${orange.bodySkew}deg)`,
          transformOrigin: "bottom center",
        }}
      >
        <div
          className="absolute flex gap-8 transition-all duration-200 ease-out"
          style={{
            left: passwordVisible ? 50 : 82 + orange.faceX,
            top: passwordVisible ? 85 : 90 + orange.faceY,
          }}
        >
          <Pupil
            forceLookX={passwordVisible ? -5 : undefined}
            forceLookY={passwordVisible ? -4 : undefined}
          />
          <Pupil
            forceLookX={passwordVisible ? -5 : undefined}
            forceLookY={passwordVisible ? -4 : undefined}
          />
        </div>
      </div>

      <div
        ref={yellowRef}
        className="absolute bottom-0 transition-all duration-700 ease-in-out"
        style={{
          left: 310,
          width: 140,
          height: 230,
          backgroundColor: "#E8D754",
          borderRadius: "70px 70px 0 0",
          zIndex: 4,
          transform: passwordVisible
            ? "skewX(0deg)"
            : `skewX(${yellow.bodySkew}deg)`,
          transformOrigin: "bottom center",
        }}
      >
        <div
          className="absolute flex gap-6 transition-all duration-200 ease-out"
          style={{
            left: passwordVisible ? 20 : 52 + yellow.faceX,
            top: passwordVisible ? 35 : 40 + yellow.faceY,
          }}
        >
          <Pupil
            forceLookX={passwordVisible ? -5 : undefined}
            forceLookY={passwordVisible ? -4 : undefined}
          />
          <Pupil
            forceLookX={passwordVisible ? -5 : undefined}
            forceLookY={passwordVisible ? -4 : undefined}
          />
        </div>
        <div
          className="absolute h-1 w-20 rounded-full bg-[#2D2D2D] transition-all duration-200 ease-out"
          style={{
            left: passwordVisible ? 10 : 40 + yellow.faceX,
            top: passwordVisible ? 88 : 88 + yellow.faceY,
          }}
        />
      </div>
    </div>
  );
}
