"use strict";

/**
 * Centralized floating menu dismissal.
 *
 * This handles all small dropdown/popover menus in one place:
 * timeframe, indicators, compare, chart settings, and scheduler.
 *
 * The menus can keep their own visual classes. This file only needs
 * to know their wrapper, trigger, and menu selectors.
 */


const FLOATING_MENUS = [
  {
    wrapper: ".timeframe-dropdown",
    trigger: "#timeframeTrigger",
    menu: "#timeframeMenu",
  },
  {
    wrapper: ".indicators-wrapper",
    trigger: "#indicators_button",
    menu: "#indicators_menu",
  },
  {
    wrapper: ".compare-wrapper",
    trigger: "#compare_button",
    menu: "#compare_menu",
  },
  {
    wrapper: ".chart-settings-wrapper",
    trigger: "#chart_settings_button",
    menu: "#chart_settings_menu",
    usesAriaHidden: true,
  },
  {
    wrapper: ".scheduler-strip",
    trigger: "#schedulerBtn",
    menu: "#schedulerPopover",
  },
];

function setFloatingMenuOpen(menuConfig, isOpen) {
  const trigger = document.querySelector(menuConfig.trigger);
  const menu = document.querySelector(menuConfig.menu);

  if (!menu) return;

  menu.classList.toggle("open", isOpen);

  if (trigger) {
    trigger.setAttribute("aria-expanded", String(isOpen));
  }

  if (menuConfig.usesAriaHidden) {
    menu.setAttribute("aria-hidden", String(!isOpen));
  }
}

function closeFloatingMenusExcept(activeWrapperSelector = null) {
  FLOATING_MENUS.forEach((menuConfig) => {
    if (menuConfig.wrapper === activeWrapperSelector) return;
    setFloatingMenuOpen(menuConfig, false);
  });
}

function closeAllFloatingMenus() {
  closeFloatingMenusExcept(null);
}

function getClickedFloatingWrapper(target) {
  const menuConfig = FLOATING_MENUS.find((config) =>
    target.closest(config.wrapper),
  );

  return menuConfig?.wrapper ?? null;
}

function initFloatingMenuDismissal() {
  document.addEventListener("click", (event) => {
    const clickedWrapper = getClickedFloatingWrapper(event.target);

    if (!clickedWrapper) {
      closeAllFloatingMenus();
      return;
    }

    closeFloatingMenusExcept(clickedWrapper);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      closeAllFloatingMenus();
    }
  });
}

initFloatingMenuDismissal();