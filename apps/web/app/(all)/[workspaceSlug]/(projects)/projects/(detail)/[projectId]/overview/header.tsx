/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { useForm } from "react-hook-form";
import { EmojiPicker, EmojiIconPickerTypes, Logo } from "@plane/propel/emoji-icon-picker";
import type { TProject } from "@plane/types";
import { CoverImage } from "@/components/common/cover-image";
import { ImagePickerPopover } from "@/components/core/image-picker-popover";

type Props = {
  project: TProject;
  disabled: boolean;
  onChange: (changes: Partial<TProject>) => Promise<void>;
};

/**
 * Banner and icon, editable in place.
 *
 * Neither needed a migration: `cover_image_asset` and `logo_props` have been on `Project`
 * all along and the create form already writes both. What was missing was a surface to
 * change them after creation, so this reuses that form's two pickers rather than growing
 * a second way to pick an image.
 *
 * `ImagePickerPopover` takes a react-hook-form `control` because it is only ever used
 * inside one today. There is no form here -- each picker writes straight through -- so a
 * throwaway form supplies the control rather than the component being rewritten to make
 * the dependency optional, which would touch every existing caller.
 */
export function OverviewHeader({ project, disabled, onChange }: Props) {
  const [isEmojiPickerOpen, setIsEmojiPickerOpen] = useState(false);
  const { control } = useForm<{ cover_image_url: string | null }>({
    defaultValues: { cover_image_url: project.cover_image_url ?? null },
  });

  const logo = project.logo_props;

  return (
    <div className="group relative h-40 w-full rounded-lg">
      <CoverImage
        src={project.cover_image_url}
        alt={`${project.name} cover image`}
        className="absolute top-0 left-0 h-full w-full rounded-lg"
      />

      {!disabled && (
        <div className="absolute right-2 bottom-2">
          <ImagePickerPopover
            label="Change cover"
            control={control}
            value={project.cover_image_url ?? null}
            projectId={project.id}
            onChange={(data) => void onChange({ cover_image: data })}
          />
        </div>
      )}

      <div className="absolute -bottom-[22px] left-3">
        <EmojiPicker
          iconType="material"
          isOpen={isEmojiPickerOpen}
          handleToggle={(open: boolean) => !disabled && setIsEmojiPickerOpen(open)}
          className="flex items-center justify-center"
          buttonClassName="flex items-center justify-center"
          label={
            <span className="grid h-11 w-11 place-items-center rounded-md border border-subtle bg-layer-2">
              <Logo logo={logo} size={20} />
            </span>
          }
          onChange={(val: any) => {
            // Same shape the create form writes, so a project looks the same however its
            // icon was set.
            const logoValue = val?.type === "emoji" ? { value: val.value } : val?.value;
            void onChange({ logo_props: { in_use: val?.type, [val?.type]: logoValue } });
            setIsEmojiPickerOpen(false);
          }}
          defaultIconColor={logo?.in_use === "icon" ? logo?.icon?.color : undefined}
          defaultOpen={logo?.in_use === "emoji" ? EmojiIconPickerTypes.EMOJI : EmojiIconPickerTypes.ICON}
        />
      </div>
    </div>
  );
}
