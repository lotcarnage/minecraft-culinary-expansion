package dev.lotcarnage.culinaryexpansion.paper;

import java.util.*;
import org.bukkit.*;
import org.bukkit.command.*;
import org.bukkit.entity.Player;
import org.bukkit.inventory.*;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.potion.*;
import net.kyori.adventure.text.Component;
import net.kyori.adventure.key.Key;
import io.papermc.paper.datacomponent.DataComponentTypes;
import io.papermc.paper.datacomponent.item.*;
import io.papermc.paper.datacomponent.item.consumable.ConsumeEffect;

public final class CulinaryExpansionPlugin extends JavaPlugin {
    final Map<String, ItemStack> items = new LinkedHashMap<>();
    final List<NamespacedKey> recipes = new ArrayList<>();
    NamespacedKey itemKey;

    @Override public void onEnable() {
        itemKey = new NamespacedKey(this, "item");
        GeneratedContent.register(this);
    }
    @Override public void onDisable() {
        recipes.forEach(key -> getServer().removeRecipe(key));
    }
    void item(String id, int stack, int nutrition, float saturation, boolean always,
              float seconds, String remainder, String effect, int ticks, int level, double probability, boolean edible) {
        ItemStack item = ItemStack.of(Material.PAPER);
        var meta = item.getItemMeta();
        meta.getPersistentDataContainer().set(itemKey, PersistentDataType.STRING, id);
        item.setItemMeta(meta);
        item.setData(DataComponentTypes.ITEM_NAME, Component.translatable("item.culinary_expansion." + id));
        item.setData(DataComponentTypes.ITEM_MODEL, Key.key("culinary_expansion", id));
        item.setData(DataComponentTypes.MAX_STACK_SIZE, stack);
        if (edible) {
            item.setData(DataComponentTypes.FOOD, FoodProperties.food().nutrition(nutrition)
                    .saturation(saturation).canAlwaysEat(always).build());
            var consumable = Consumable.consumable().consumeSeconds(seconds);
            if (!remainder.isEmpty()) item.setData(DataComponentTypes.USE_REMAINDER,
                    UseRemainder.useRemainder(ItemStack.of(Material.valueOf(remainder))));
            if (!effect.isEmpty()) {
                PotionEffectType type = Registry.EFFECT.get(NamespacedKey.minecraft(effect.toLowerCase(Locale.ROOT)));
                if (type == null) throw new IllegalArgumentException("Unknown effect: " + effect);
                consumable.addEffect(ConsumeEffect.applyStatusEffects(
                        List.of(new PotionEffect(type, ticks, level)), (float) probability));
            }
            item.setData(DataComponentTypes.CONSUMABLE, consumable.build());
        }
        items.put(id, item);
    }
    ItemStack result(String id, int count) {
        ItemStack item = Objects.requireNonNull(items.get(id), "Unknown item: " + id).clone();
        item.setAmount(count);
        return item;
    }
    RecipeChoice ingredient(String id) {
        if (id.startsWith("culinary_expansion:")) {
            String name = id.substring(id.indexOf(':') + 1);
            return RecipeChoice.predicateChoice(candidate -> candidate.hasItemMeta() && name.equals(
                    candidate.getItemMeta().getPersistentDataContainer().get(itemKey, PersistentDataType.STRING)),
                    result(name, 1));
        }
        Material material = Material.matchMaterial(id);
        if (material == null) throw new IllegalArgumentException("Unknown ingredient: " + id);
        return new RecipeChoice.MaterialChoice(material);
    }
    NamespacedKey recipeKey(String id) { return new NamespacedKey("culinary_expansion", id); }
    void recipe(Recipe recipe) {
        if (!getServer().addRecipe(recipe)) throw new IllegalStateException("Duplicate recipe: " + recipe);
        recipes.add(((Keyed) recipe).getKey());
    }
    @Override public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) { sender.sendMessage("Players only."); return true; }
        if (args.length != 1 || !items.containsKey(args[0])) {
            sender.sendMessage("/culinary <" + String.join("|", items.keySet()) + ">"); return true;
        }
        player.getInventory().addItem(result(args[0], 1)).values().forEach(
                item -> player.getWorld().dropItemNaturally(player.getLocation(), item));
        return true;
    }
}
