package dev.lotcarnage.culinaryexpansion;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;
@Mod("culinary_expansion")
public final class CulinaryExpansion {
    public CulinaryExpansion(FMLJavaModLoadingContext context) { ModItems.register(context); }
}
